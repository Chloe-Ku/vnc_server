from sqldb import SQLDB
from response import Response
from datetime import datetime, timedelta
import logging
logger = logging.getLogger(__name__)
class Coordinates(object):
    

    def __init__(self):
        self.db = SQLDB()



    def insertPolyline(self, polyline):
        cols = [
                'adminEmail',
                'mapName',
                'polyline',
                'node'
        ]
        colsSQL   = ', '.join(cols)
        valuesSQL = ', '.join(['%s' for _c in cols])

              
        sql = 'INSERT INTO Maps (%s) VALUES (%s)' % (colsSQL, valuesSQL)
        logger.debug(polyline)
        args = tuple(polyline)
        logger.debug(args)
        
        self.executeOne(sql, args)


        return Response(True, 'Successfully inserted polyline')
    def insertNode(self, circle):
        cols = [
                'adminEmail',
                'mapName',
                'polyline',
                'node'
        ]
        colsSQL   = ', '.join(cols)
        valuesSQL = ', '.join(['%s' for _c in cols])

              
        sql = 'INSERT INTO Maps (%s) VALUES (%s)' % (colsSQL, valuesSQL)
        logger.debug(circle)
        args = tuple(circle)
        logger.debug(args)
        
        self.executeOne(sql, args)


        return Response(True, 'Successfully inserted Node')
    
    def getMaps(self,email):
        table = 'Maps'

        selectCols = [
            'mapName',
           
        ]

        whereCols = [
            'adminEmail'
        ]

        whereObj = {
            c: email
            for c in whereCols
        }

        tuples = self.read(table, selectCols, whereCols, whereObj)
        
        return tuples.results


    def deleteMap(self, map,adminEmail):
        
        r = self.delete('Maps', ['mapName' , 'adminEmail'], {"mapName": map , "adminEmail" : adminEmail})
        
        if r.success:
            return Response(True, 'Successfully deleted map')
        else: 
            return Response(False, 'could not deleted map')
            
    def getCoordinates(self,map,email):
        table = 'Maps'
        
        

        tuples = self.read(table, ['polyline'], ['mapName' , 'adminEmail', 'node'], {"mapName": map , "adminEmail" : email, "node" : "NULL"})
        polylineTuples = tuples.results
        tuples = self.read(table, ['node'], ['mapName' , 'adminEmail', 'polyline'], {"mapName": map , "adminEmail" : email, "polyline" : "NULL"})
        nodesTuples = tuples.results
        Dict = {'Polylines' : polylineTuples, "Nodes" : nodesTuples}
        return Dict