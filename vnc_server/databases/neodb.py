from neo4j import GraphDatabase

import json
from response import Response

from pprint import pprint

#
# This class should be the only code that interacts with Neo4j.
# In other words, NeoDB is the interface between Neo4j
# and the rest of this project.
#
class NeoDB(object):

    _uri = "bolt://localhost:7687"

    def __init__(self):
        self.driver = GraphDatabase.driver(NeoDB._uri)


    #
    # Executes one statement in one transaction.
    #
    # During a CREATE, remember to return the created item to get its ID
    # (via the `id` field).
    #
    # @param cypher Neo4j command to be executed
    # @param args map from the cypher string's variables to their values
    #
    def executeOne(self, cypher, args):
        # with self.driver.session() as session:
        #     return session.run(cypher, args).values()

        with self.driver.session() as session:
            tx = session.begin_transaction()
            ret = tx.run(cypher, args).values()
            tx.commit()
            return ret


    #
    # Executes many statements in one transaction.
    #
    # During a CREATE, remember to return the created item to get its ID
    # (via the `id` field).
    #
    # @param commands list of tuples that are (cypher, args),
    #     where cypher is the Neo4j command,
    #     and args is the map from the cypher string's variables to their values
    #
    def executeMany(self, commands):
        with self.driver.session() as session:

            tx = session.begin_transaction()

            ret = []

            for command in commands:
                cypher = command[0]
                args   = command[1]
                ret.append(tx.run(cypher, args).values())

            tx.commit()

            return ret


    #
    # Here, 'Graph' refers to the EcoPRT network of nodes and edges.
    #
    def getGraph(self):
        try:
            cypher = 'MATCH (n1)-[r]->(n2) ' \
                     'RETURN n1, r, n2'
            args = {}

            paths = self.executeOne(cypher, args)

            # nodes1 = []
            # edges  = []
            # nodes2 = []
            # for p in paths:
            #     nodes1.append({k: v for (k, v) in p[0].items()})
            #     edges.append({k: v for (k, v) in p[1].items()})
            #     nodes2.append({k: v for (k, v) in p[2].items()})

            theGraph = {
                'vertices': {},
                'edges': {}
            }

            for p in paths:
                node1 = {k: v for (k, v) in p[0].items()}
                edge  = {k: v for (k, v) in p[1].items()}
                node2 = {k: v for (k, v) in p[2].items()}

                edge['vertex1'] = node1['name']
                edge['vertex2'] = node2['name']

                theGraph['vertices'][node1['name']] = node1
                theGraph['vertices'][node2['name']] = node2
                theGraph['edges'][edge['name']] = edge

            return Response(True, 'Successfully got the Graph', results=theGraph)
        except Exception as e:
            return Response(False, 'Failed to get the Graph: %s' % e)


    #
    # USE THIS FUNCTION WITH CAUTION
    #
    def deleteEverytyhing(self):
        try:
            cypher = 'MATCH (n) ' \
                     'DETACH DELETE n'
            args = {}

            self.executeOne(cypher, args)

            return Response(True, 'Successfully deleted everything')
        except Exception as e:
            print('Exception during deleteEverytyhing(): %s' % e)
            return Response(False, 'Failed to delete everything')


    def getAllNodes(self):
        try:
            cypher = 'MATCH (n) ' \
                     'RETURN n'
            args = {}

            paths = self.executeOne(cypher, args)
            nodes = [p[0] for p in paths]
            
            nodeAttribs = [
                {k: v for (k, v) in n.items()}
                for n in nodes
            ]

            return Response(True, 'Successfully got all Nodes', results=nodeAttribs)
        except Exception as e:
            print('Exception during getAllNodes(): %s' % e)
            return Response(False, 'Failed to get all Nodes')


    def getAllPaths(self, directed=True):
        try:
            if (directed):
                cypher = 'MATCH (n1)-[r]->(n2) ' \
                     'RETURN n1, r, n2'
            else:
                cypher = 'MATCH (n1)-[r]-(n2) ' \
                     'RETURN n1, r, n2'
            
            args = {}

            paths = self.executeOne(cypher, args)

            return Response(True, 'Successfully got all Paths', results=paths)
        except Exception as e:
            print('Exception during getAllPaths(): %s' % e)
            return Response(False, 'Failed to get all Paths')


    def loadGraph(self, filepath):
        try:
            with open(filepath, 'r') as f:
                jsonObj = json.loads(f.read())

            commands = []
            for edge in jsonObj['graph']['edges']:
                # NOTE: Neo4j only allows directed relationships.
                # We just have to ignore the direciton later on.
                # The vertices have to be MERGEd, but I chose to MERGE the edge
                # to be idempotent
                cypher = 'MERGE (v1:Waypoint {longitude: $long1, latitude: $lat1, hub: $hub1, name: $name1, weight: $weight1}) ' \
                         'MERGE (v2:Waypoint {longitude: $long2, latitude: $lat2, hub: $hub2, name: $name2, weight: $weight2}) ' \
                         'MERGE (v1)-[e:CONNECTED {distance: $dist, name: $eName}]->(v2)'

                args = {
                    'long1':   edge['vertex1']['longitude'],
                    'lat1':    edge['vertex1']['latitude'],
                    'hub1':    edge['vertex1']['hub'],
                    'name1':   edge['vertex1']['name'],
                    'weight1': edge['vertex1']['weight'],
                    'long2':   edge['vertex2']['longitude'],
                    'lat2':    edge['vertex2']['latitude'],
                    'hub2':    edge['vertex2']['hub'],
                    'name2':   edge['vertex2']['name'],
                    'weight2': edge['vertex2']['weight'],
                    'dist':    edge['distance'],
                    'eName':   edge['name']
                }

                commands.append((cypher, args))

            self.executeMany(commands)

            return Response(True, 'Successfully loaded graph!')
        except Exception as e:
            return Response(False, 'Failed to load graph: %s' % e)





    #
    # Below is the remnants of when we thought that we were going to
    # store the queue of Rides in Neo4j.
    # We actually just have it stored in MySQL.
    #
    # Keeping this code lying around in case it's useful in the future.
    #

    def createRidesQueue(self):
        try:
            cypher = 'CREATE (s:RidesStart:RidesQueue)-[r:NEXT]->(e:RidesEnd:RidesQueue) ' \
                     'RETURN s, r, e'
            args = {}

            results = self.executeOne(cypher, args)
            assert(len(results) == 1)

            thePath = results[0]
            assert(len(thePath) == 3)

            return Response(True, 'Successfully created rides queue')
        except Exception as e:
            print('Exception during createRidesQueue(): %s' % e)
            return Response(False, 'Failed to create rides queue: %s' % e)


    def enqueueRide(self, ride):
        try:
            getLockCypher = 'MATCH (q1)-[r:NEXT]->(q2) ' \
                            'SET    q1._lock = true '    \
                            'SET     r._lock = true '    \
                            'SET    q2._lock = true '
            getLockArgs = {}


            # 1) Create a new Ride "newride"
            # 2) Link the back of the queue to newride
            # 3) Link newride to End
            # 4) De-link the (old) back of the queue from End
            enqueueCypher = 'CREATE (newride:Ride:RidesQueue) '                                 \
                            'WITH newride '                                                     \
                            'MATCH (back:RidesQueue)-[oldrel:NEXT]->(end:RidesEnd:RidesQueue) ' \
                            'CREATE (back)-[:NEXT]->(newride) '                                 \
                            'CREATE (newride)-[:NEXT]->(end) '                                  \
                            'DELETE oldrel '                                                    \
                            'RETURN newride'
            enqueueArgs = {}

            # results = self.executeOne(enqueueCypher, args)
            # assert len(results) == 1, 'Rides queue does not exist!'
            # assert len(results[0]) == 1, 'Rides queue exists, but new Ride could not be enqueued!'

            resultsList = self.executeMany([(getLockCypher, getLockArgs), (enqueueCypher, enqueueArgs)])
            results = resultsList[1]
            assert len(results) == 1, 'Rides queue does not exist!'
            assert len(results[0]) == 1, 'Rides queue exists, but new Ride could not be enqueued!'

            return Response(True, 'Successfully enqueued ride')
        except Exception as e:
            print('Exception during enqueueRide(): %s' % e)
            return Response(False, 'Failed to enqueue ride: %s' % e)

    def dequeueRide(self):
        try:
            getLockCypher = 'MATCH (q1)-[r:NEXT]->(q2) ' \
                            'SET    q1._lock = true '    \
                            'SET     r._lock = true '    \
                            'SET    q2._lock = true '
            getLockArgs = {}

            # 1) De-link Start from the front of the queue "front"
            # 2) De-link front from (previously) second item
            # 3) Link Start to (previously) second item
            dequeueCypher = 'MATCH (start:RidesStart:RidesQueue)-[:NEXT]->(front:RidesQueue)-[:NEXT]->(second:RidesQueue) ' \
                            'DETACH DELETE front '                                                                         \
                            'CREATE (start)-[:NEXT]->(second) '                                                            \
                            'RETURN front'
            dequeueArgs = {}

            resultsList = self.executeMany([(getLockCypher, getLockArgs), (dequeueCypher, dequeueArgs)])
            paths = resultsList[1]

            if (len(paths) == 0):
                return Response(True, 'Successfully dequeued ride - but none existed')
            else:
                return Response(True, 'Successfully dequeued ride', results=paths[0])
        except Exception as e:
            print('Exception during dequeueRide(): %s' % e)
            return Response(False, 'Failed to dequeue ride: %s' % e)

