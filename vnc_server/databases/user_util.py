from sqldb import SQLDB
from response import Response
from datetime import datetime, timedelta

import base64
import os
import random
import hashlib


class UserUtil(object):

    alphabet = '0123456789abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ'

    def __init__(self):
        self.db = SQLDB()


    def _genUser(self):
        return {
            'fname':    'Lucas',
            'lname':    'Molander',
            'email':    'lmmoland@ncsu.edu',
            'type':     'admin',
            'password': 'thebestpassword',
            'extID':    None,
            'extType':  None
        }


    def insertUser(self, user):
        """
        User should have at least the fields fname, lname, email, and password
        """
        try:
            if self.validateUser(user).message == 'User not found':
                user['salt'] = ''.join(random.choice(UserUtil.alphabet) for i in range(16))
                user['hash'] = hashlib.sha512((user['salt'] + user['password']).encode('utf-8')).hexdigest()
                user['type'] = 'USER'

                cols = [
                    'fname',
                    'lname',
                    'email',
                    'type',
                    'salt',
                    'hash'
                ]
                colsSQL   = ', '.join(cols)
                valuesSQL = ', '.join(['%s' for _c in cols])

                # e.g. INSERT INTO Users (fname) VALUES (%s)
                sql = 'INSERT INTO Users (%s) VALUES (%s)' % (colsSQL, valuesSQL)
                args = tuple(user[c] for c in cols)

                self.db.executeOne(sql, args)

                # Remove password from user object before returning
                del user['password']

                return Response(True, 'Successfully inserted user', results=user)
            return Response(False, 'An account with the provided email already exists')
        except Exception as e:
            return Response(False, 'Failed to insert user: %s' % e)


    def validateUser(self, user):
        """
        User should have at least the fields email and password.
        """
        try:
            table = 'Users'

            selectCols = [
                'email',
                'fname',
                'lname',
                'salt',
                'hash'
            ]

            whereCols = [
                'email'
            ]

            whereObj = {
                c: user[c]
                for c in whereCols
            }

            users = self.db.read(table, selectCols, whereCols, whereObj)
            if (len(users.results) == 0):
                return Response(False, 'User not found')

            theUser = users.results[0]

            newHash = hashlib.sha512((theUser['salt'] + user['password']).encode('utf-8')).hexdigest()
            if (newHash == theUser['hash']):
                return Response(True, 'Passwords match', results=theUser)
            else:
                return Response(False, 'Incorrect password')
        except Exception as e:
            return Response(False, 'Failed to validate user: %s' % e)

    def insertGoogleUser(self, user):
        """
        Insert Google user to DB.
        """
        try:
            user['type'] = 'USER'
            user['extType'] = 'GOOGLE'
            cols = [
                'fname',
                'lname',
                'email',
                'type',
                'extType'
            ]
            colsSQL   = ', '.join(cols)
            valuesSQL = ', '.join(['%s' for _c in cols])

            # e.g. INSERT INTO Users (fname) VALUES (%s)
            sql = 'INSERT INTO Users (%s) VALUES (%s)' % (colsSQL, valuesSQL)
            args = tuple(user[c] for c in cols)

            self.db.executeOne(sql, args)

            return Response(True, 'Successfully inserted Google user', results=user)
        except Exception as e:
            return Response(False, 'Failed to insert Google user: %s' % e)

    def validateGoogleUser(self, user):
        """
        Check if a Google user's email exists in the DB. If not add it to the DB.
        """
        try:
            table = 'Users'

            selectCols = [
                'email',
                'fname',
                'lname'
            ]

            whereCols = [
                'email'
            ]

            whereObj = {
                c: user[c]
                for c in whereCols
            }

            users = self.db.read(table, selectCols, whereCols, whereObj)
            if (len(users.results) == 0):
                self.insertGoogleUser(user)
                theUser = user
            else:
                theUser = users.results[0]

            self.get_token(theUser)
            return Response(True, 'Google user validated', results=theUser)
        except Exception as e:
            return Response(False, 'Failed to validate Google user: %s' % e)

    def updateAuthToken(self, user, authToken):
        try:
            table = 'Users'

            setObj = {
                'authToken': authToken
            }

            whereCols = [
                'email'
            ]

            whereObj = {
                c: user[c]
                for c in whereCols
            }

            self.db.update(table, setObj, whereObj)

            return Response(True, 'Successfully updated auth token')
        except Exception as e:
            return Response(False, 'Failed to update auth token for user: %s' % e)

    def updateTokenExpiration(self, user, tokenExpiration):
        try:
            table = 'Users'

            setObj = {
                'token_expiration': tokenExpiration
            }

            whereCols = [
                'email'
            ]

            whereObj = {
                c: user[c]
                for c in whereCols
            }

            self.db.update(table, setObj, whereObj)

            return Response(True, 'Successfully updated auth token')
        except Exception as e:
            return Response(False, 'Failed to update auth token for user: %s' % e)

    def updateUser(self, user):
        try:
            table = 'Users'

            setObj = {
                'email': user['email'],
                'fname': user['fname'],
                'lname': user['lname']
            }

            if user['password'] != '':
                setObj['salt'] = ''.join(random.choice(UserUtil.alphabet) for i in range(16))
                setObj['hash'] = hashlib.sha512((setObj['salt'] + user['password']).encode('utf-8')).hexdigest()

            whereObj = {
                'email': user['oldEmail']
            }

            self.db.update(table, setObj, whereObj)

            return Response(True, 'Successfully updated user')
        except Exception as e:
            return Response(False, 'Failed to update user: %s' % e)

    def get_token(self, user, expires_in=3600):
        now = datetime.utcnow()
        if 'authToken' in user.keys() and user['authToken'] and user['token_expiration'] > now + timedelta(seconds=60):
            return user['authToken']
        user['authToken'] = base64.b64encode(os.urandom(24)).decode('utf-8')
        user['token_expiration'] = now + timedelta(seconds=expires_in)
        self.updateAuthToken(user, user['authToken'])
        self.updateTokenExpiration(user, user['token_expiration'])
        return user['authToken']

    def revoke_token(self, user):
        user['token_expiration'] = datetime.utcnow() - timedelta(seconds=1)

        try:
            table = 'Users'

            setObj = {
                'token_expiration': user['token_expiration']
            }

            whereCols = [
                'email'
            ]

            whereObj = {
                c: user[c]
                for c in whereCols
            }

            self.db.update(table, setObj, whereObj)

            return Response(True, 'Successfully revoked token')
        except Exception as e:
            return Response(False, 'Failed to revoke token for user: %s' % e)

    @staticmethod
    def check_token(authToken):
        db = SQLDB()
        #Find user with given token (If exists)
        table = 'Users'

        selectCols = [
            'email',
            'authToken',
            'token_expiration'
        ]

        whereCols = [
            'authToken'
        ]

        whereObj = {
            c: authToken
            for c in whereCols
        }

        users = db.read(table, selectCols, whereCols, whereObj)
        if (len(users.results) == 0):
            return Response(False, 'User not found')
        user = users.results[0]

        if user is None or user['token_expiration'] < datetime.utcnow():
            return None
        return user
