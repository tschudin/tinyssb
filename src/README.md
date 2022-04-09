# Source code for tinySSB

## Relevant

- [lora-bridge](lora-bridge) Arduino code for Heltec ESP32


## Informational

- [poc-01](poc-01) proof-of-concept of "predictive gossip" in Python and Micropython: this demos one producer and two consumers, showing the reliable replication of tinySSB frames despite them not having a FeedID or SEQ field. This PoC includes a first version of the tinySSB Python library.
- [poc-02](poc-02) proof-of-concept of a __chat app__ with three preinstalled users and a simple command line interface similar to "UNIX mail". This PoC was made to complement the previous PoC for tri-directional log replication as well as the replication of long blob sidechains. The README contains a some insights and a diagram of the software structure.
- [poc-03](poc-03) proof-of-concept tools for creating feed hierarchies, including an explanation of the concept in the README. Additionally, a dump utility is provided that expands the content of binary log entries and pretty-prints them in JSON. This PoC contains the most recent ```tinyssb``` Python library.
