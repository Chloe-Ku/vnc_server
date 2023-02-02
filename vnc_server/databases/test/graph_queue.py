from threading import Thread
from ride_util import RideUtil

def testQueue(nProd, rPerProd, nCons, rPerCons):
    ru = RideUtil()

    def produce(ru, nToProduce):
        for _i in range(0, nToProduce):
            ru.enqueueRide(None)

    def consume(ru, nToConsume):
        for _i in range(0, nToConsume):
            ru.dequeueRide()
    #
    # Create the threads (and their associated connections)
    #
    prodThreads = []
    consThreads = []

    prodConns = [RideUtil() for _i in range(0, nProd)]
    consConns = [RideUtil() for _i in range(0, nCons)]

    for i in range(0, nProd):
        t = Thread(target=produce, args=(prodConns[i], rPerProd))
        prodThreads.append(t)

    for i in range(0, nCons):
        t = Thread(target=consume, args=(consConns[i], rPerCons))
        consThreads.append(t)

    #
    # Run the threads
    #
    for pt in prodThreads:
        pt.start()

    for ct in consThreads:
        ct.start()

    #
    # Wait for the threads
    #
    for pt in prodThreads:
        pt.join()

    for ct in consThreads:
        ct.join()


def main():
    testQueue(100, 10, 0, 5)


if __name__ == '__main__':
    main()



