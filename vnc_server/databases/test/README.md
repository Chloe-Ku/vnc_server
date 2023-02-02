# Database Tests

This folder contains scripts that test the database layer in a non-trivial way.
For example, if we wanted to test massive concurrency, we would want to make a shell script or python script that hammers the database, and place that file here.
However, if we just wanted to have a file for quick development purposes, we would want to name it something like `test.py` and keep it in the directory above this one.

## `graph_queue.py`

This file tests concurrency of editing the Rides queue.
Since this file's creation, we have decided to simply keep the queue of Rides in memory.
There's no real reason to persist current Rides information (although we will want to visit a Rides History later, but that's easily handled).
