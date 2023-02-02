#
# This file just contains a class that defines static methods
# that are useful for communicating objects (commands, specifically)
# between the server and the client.
#

import json
import struct
import socket


class Communication(object):
    # Represent message size with a standard int for now
    msgSizeLen = 4

    # How to represent the integer length in bytes
    intByteRep = ">I"

    #
    # No constructor because this is for static methods
    #

    def __init__(self):
        pass

    #
    # To send an object, it is:
    #   1) Serialized to JSON
    #   2) Converted from that JSON string to an array of bytes
    #   3) The length of that bytes array is sent (length MUST be 4 bytes wide)
    #   4) The bytes array itself is sent
    #

    @staticmethod
    def sendObject(sock, obj):
        # Get the JSON string then bytes array
        objJSON = json.dumps(obj)
        # print(objJSON)
        objJSONBytes = objJSON.encode()

        # Get the length of the bytes array, then represent that as bytes too
        objJSONBytesLength = len(objJSONBytes)
        lengthBytes = struct.pack(Communication.intByteRep, objJSONBytesLength)

        # The number of bytes of the object must be represented with and exact number of bytes
        if (len(lengthBytes) != Communication.msgSizeLen):
            raise Exception('Serialized object bytes length length != %d; was %s' % (
                Communication.msgSizeLen, len(lengthBytes)))

        # Send the size of the object then the object itself
        # (in one sendall() to be slightly more efficient)
        sock.sendall(lengthBytes + objJSONBytes)

    #
    # To receive an object, it:
    #   1) Receives the bytes representin the length of the bytes array
    #   2) Converts that to an integer
    #   3) Receives that many bytes (the whole object)
    #   4) Decodes that to a JSON string
    #   5) Deserializes that JSON string to an object
    #

    @staticmethod
    def recvObject(sock):
        # Get the length of the object
        # MSG_WAITALL is like how sendall guarantees to send all data
        lengthBytes = sock.recv(Communication.msgSizeLen, socket.MSG_WAITALL)
        objJSONBytesLength = struct.unpack(
            Communication.intByteRep, lengthBytes)[0]

        # Now get the object itself
        objJSONBytes = sock.recv(objJSONBytesLength, socket.MSG_WAITALL)
        objJSON = objJSONBytes.decode('utf-8')
        obj = json.loads(objJSON)

        return obj
