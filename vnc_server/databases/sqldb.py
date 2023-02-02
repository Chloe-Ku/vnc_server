import pymysql
from pprint import pprint

from response import Response

class SQLDB(object):
    def __init__(self):
        #
        # Create the connection
        #
        args = {
            'host':     'localhost',
            'user':     'root',
            'password': 'root',
            'db':       'EcoPRT'
        }
        # self.conn = pymysql.connect(args)
        self.conn = pymysql.connect(host='localhost', user='root', password='root', db='EcoPRT')

        #
        # Reflect the list of tables and associated columns into memory.
        #
        self.tables = [r[0] for r in self.executeOne('SHOW TABLES', tuple())]

        # Map from table name to list of objects,
        # each of which has a 'name' and 'type' field.
        # List to maintain order and correlation between name and type.
        self.tableInfo = {}
        for t in self.tables:
            columnInfos = [r[0:2] for r in self.executeOne('SHOW COLUMNS FROM %s' % t, tuple())]
            self.tableInfo[t] = [{'name': ci[0], 'type': ci[1]} for ci in columnInfos]
    
    def __del__(self):
        """The is a destructor method that closes the MySQL connection when the object is deleted
        """
        self.conn.close()

    def executeOne(self, sql, args):
        """
        NOTE that args is a tuple!!!
        """

        # print('\nexecuteOne():')
        # print('\tSQL: %s' % sql)
        # print('\targs: tuple(%s)\n' % list(args))

        with self.conn.cursor() as cursor:
            cursor.execute(sql, args)
            results = list(cursor.fetchall())

        self.conn.commit()

        #
        # Convert from bytes (VARBINARY) to string
        #
        newResults = []
        for r in results:
            newR = []
            for v in r:
                if (v is not None and type(v).__name__ == 'bytes'):
                    newR.append(v.decode('utf-8'))
                else:
                    newR.append(v)
            newResults.append(tuple(newR))

        return newResults


    def create(self, table, cols, obj):
        colsSQL = ', '.join(cols)

        valsSQL = ', '.join(['%s' for c in cols])

        sql = 'INSERT INTO %s (%s) VALUES (%s)' % (table, colsSQL, valsSQL)
        args = tuple([obj[c] for c in cols])

        try:
            self.executeOne(sql, args)
            return Response(True, 'Successfully created.')
        except Exception as e:
            return Response(False, str(e))


    def read(self, table, selectCols, whereCols, obj):
        if (whereCols is None):
            whereCols = []

        if (selectCols == '*'):
            colsSQL = '*'
        else:
            colsSQL = ', '.join(selectCols)

        whereSQL = ' AND '.join(['%s=%%s' % wc for wc in whereCols])

        if (len(whereCols) > 0):
            sql = 'SELECT %s FROM %s WHERE %s' % (colsSQL, table, whereSQL)
        else:
            sql = 'SELECT %s FROM %s' % (colsSQL, table)

        args = tuple(obj[wc] for wc in whereCols)

        try:
            results = self.executeOne(sql, args)
        except Exception as e:
            return Response(False, str(e))

        # Convert from tuples to maps
        out = []
        for res in results:
            if (selectCols == '*'):
                # Use the reflected list of columns to determine order
                out.append({
                    colInfo['name']: res[i]
                    for i, colInfo in enumerate(self.tableInfo[table])
                })
            else:
                out.append({
                    c: res[i]
                    for i, c in enumerate(selectCols)
                })

        return Response(True, 'Successfully read.', results=out)


    def update(self, table, setAttrs, whereAttrs):
        if (whereAttrs == None):
            whereAttrs = {}

        setCols   = list(setAttrs.keys())
        whereCols = list(whereAttrs.keys())

        setStuff   = ['%s=%%s' % sc for sc in setCols]
        whereStuff = ['%s=%%s' % wc for wc in whereCols]

        setSQL   = ', '.join(setStuff)
        whereSQL = ' AND '.join(whereStuff)

        if (len(whereCols) > 0):
            sql = 'UPDATE %s SET %s WHERE %s' % (table, setSQL, whereSQL)
        else:
            sql = 'UPDATE %s SET %s' % (table, setSQL)

        values = [setAttrs[sc] for sc in setCols]
        values.extend([whereAttrs[wc] for wc in whereCols])
        args = tuple(values)

        try:
            self.executeOne(sql, args)
            return Response(True, 'Successfully updated.')
        except Exception as e:
            return Response(False, str(e))


    def delete(self, table, whereCols, obj):
        if (whereCols == None):
            whereCols = []

        whereSQL = ' AND '.join(['%s=%%s' % wc for wc in whereCols])

        if (len(whereCols) > 0):
            sql = 'DELETE FROM %s WHERE %s' % (table, whereSQL)
        else:
            sql = 'DELETE FROM %s' % table

        args = tuple([obj[wc] for wc in whereCols])

        try:
            self.executeOne(sql, args)
            return Response(True, 'Successfully deleted.')
        except Exception as e:
            return Response(False, str(e))
