# Database Python

This folder contains `sqldb.py` and `neodb.py`. These represent a way to interact with MySQL and Neo4j (respectively) in Python. There are a few other files for more specific, one-off use-cases.

# MySQL

`sqldb.py` provides a generic CRUD interface for MySQL in the form of the class SQLDB.

# Neo4j

`neodb.py` provides a specific CRUD interface for Neo4j in the form of the class NeoDB. If you are unfamiliar with Neo4j, it is a graph-based database ([read more here](https://neo4j.com/)).

## Neo4j Driver Overview

Both session and transaction objects have `run()`, and in both cases, `run()` returns a `BoltStatementResult` whose `values()` method returns a list of paths, which are each represented by a list of `Node` and `Relationship` objects. All `Node` and `Relationship` objects have a `graph` field which is a reference to the `Graph` object that represents the graph gleaned from the executed query.

## Neo4j Driver Details

This section contains important details about the Neo4j driver objects.

### Node

`Node` has a few important fields:

| Field     | Description                                                       |
|:----------|:------------------------------------------------------------------|
| `items()` | Returns a `dict_items` of this `Node`'s attributes                |
| `labels`  | `frozen_set` of this `Node`'s labels                              |
| `id`      | ID of this `Node` (used internally by Neo4j)                      |
| `graph`   | Reference to the `Graph` object generated from the executed query |

### Relationship

`Relationship` has even more important fields than `Node`:

| Field        | Description                                                       |
|:-------------|:------------------------------------------------------------------|
| `items()`    | Returns a `dict_items` of this `Relationship`'s attributes        |
| `type`       | This `Relationship`'s type                                        |
| `start`      | ID of the start `Node`                                            |
| `end`        | ID of the end `Node`                                              |
| `start_node` | Reference to the start `Node`                                     |
| `end_node`   | Reference to the end `Node`                                       |
| `id`         | ID of this `Relationship` (used internally by Neo4j)              |
| `graph`      | Reference to the `Graph` object generated from the executed query |

### Graph

`Graph` has two fields of interest:

| Field                        | Description                 |
|:-----------------------------|:----------------------------|
| `nodes._entity_dict`         | Map from ID to Node         |
| `relationships._entity_dict` | Map from ID to Relationship |

These might be useful at some point in a wrapper.

## License
Neo4j is subject the GPLv3 license [found here](http://www.gnu.org/licenses/quick-guide-gplv3.html).

