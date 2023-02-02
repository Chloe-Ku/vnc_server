#
# Use this file to rapidly test things.
#
from pprint import pprint

from sqldb import SQLDB
from neodb import NeoDB

def testRead():
    # Ideally, these should be all static and be passed a session,
    # but we're not that cool yet.
    sqldb = SQLDB()

    # def read(self, table, selectCols, whereCols, obj):
    response = sqldb.read('Users', '*', [], None)
    print('\n')
    pprint(response.message)
    pprint(response.results)

    response = sqldb.read('Users', ['email', 'lname'], None, None)
    print('\n')
    pprint(response.message)
    pprint(response.results)

    response = sqldb.read('Users', ['email', 'lname'], ['email'], {'email': 'lmmoland@ncsu.edu'})
    print('\n')
    pprint(response.message)
    pprint(response.results)

    response = sqldb.read('Users', '*', ['email'], {'email': 'lmmoland@ncsu.edu'})
    print('\n')
    pprint(response.message)
    pprint(response.results)

    response = sqldb.read('Users', ['fname', 'lname'], ['email', 'type'], {'email': 'lmmoland@ncsu.edu', 'type': 'ADMIN'})
    print('\n')
    pprint(response.message)
    pprint(response.results)


def testCreate():
    sqldb = SQLDB()

    # def create(self, table, cols, obj):
    aVehicle = {
        'name':        'My first vehicle',
        'enabled':     0,
        'batteryLife': 100,
        'curEdge':     None,
        'curRideID':   None
    }
    response = sqldb.create('Vehicles', list(aVehicle.keys()), aVehicle)
    print(response.message)

    aVehicle = {
        'name':        'Second vehicle',
        'enabled':     1,
        'batteryLife': 30,
        'curEdge':     None,
        'curRideID':   None
    }
    response = sqldb.create('Vehicles', list(aVehicle.keys()), aVehicle)
    print(response.message)


def testUpdate():
    sqldb = SQLDB()

    # def update(self, table, setAttrs, whereAttrs):
    response = sqldb.update('Users', {'fname': 'Updated'}, {'email': 'lmmoland@ncsu.edu'})
    print(response)

    response = sqldb.update('Users', {'fname': 'SERVE THE OVERLORDS'}, None)
    print(response)


def testDelete():
    sqldb = SQLDB()

    # def delete(self, table, whereCols, obj):
    response = sqldb.delete('Vehicles', ['name'], {'name': 'My vehicle'})
    print(response)

    response = sqldb.delete('Vehicles', None, None)
    print(response)


def testLoadGraph():
    neodb = NeoDB()
    neodb.loadGraph('../neo_util/mygraph.gen.json')

def main():
    # testRead()
    # testCreate()
    # testUpdate()
    # testDelete()
    testLoadGraph()
    pass
    

if __name__ == "__main__":
    main()
