# SDN Network Diagnostic and Path Analysis Tool

**Team:** Adithya, Bhuvan, Keerthana  
**Project:** SDN-Socket Programming Mini Project  
**Project Number:** 13  
**Communication Protocol:** UDP

---

## 1. Project Overview

The SDN Network Diagnostic and Path Analysis Tool is a Software-Defined Networking (SDN) based application designed to monitor network performance, identify communication problems, and analyse network paths.

The project uses a Ryu SDN controller and Mininet to create and manage a programmable network topology.

It performs UDP-based network diagnostics to measure:

- Round Trip Time (RTT)
- Packet Loss
- Network Jitter
- Communication status

The collected measurements are reported to a REST API and analysed to identify network failures and correlate network performance with available paths.

## 2. Objectives

1. Implement a programmable SDN network using Ryu and Mininet.
2. Discover network topology dynamically using LLDP.
3. Calculate optimal network paths using Dijkstra's algorithm.
4. Identify alternative paths between network hosts.
5. Measure network performance using UDP socket programming.
6. Detect packet loss, latency, and jitter.
7. Report diagnostic measurements through a REST API.
8. Analyse measurements and identify potential network failures.

## 3. Technologies Used

| Technology | Purpose |
|---|---|
| Python 3 | Application development |
| Ryu | SDN controller |
| Mininet | Network emulation |
| Open vSwitch | Software-based switching |
| OpenFlow 1.3 | Controller-switch communication |
| UDP Sockets | Network diagnostics |
| NetworkX | Graph and path analysis |
| REST API | Diagnostic data communication |
| JSON | Data storage and exchange |

## 4. System Architecture

The project consists of four major components.

### 4.1 SDN Controller

The Ryu controller manages the network switches and implements forwarding and path selection.

Responsibilities:
- Switch management.
- Topology discovery using LLDP.
- Shortest-path calculation using Dijkstra's algorithm.
- Alternative path identification.
- Network forwarding decisions.

### 4.2 Network Topology

The network is implemented using Mininet.

It consists of:
- Four switches: s1, s2, s3, s4.
- Four hosts: h1, h2, h3, h4.
- Two alternative routes between the main communication endpoints.

The topology uses different link delays to simulate different network conditions.

| Link | Delay |
|---|---|
| s1 - s2 | 5 ms |
| s2 - s4 | 5 ms |
| s1 - s3 | 20 ms |
| s3 - s4 | 20 ms |

This allows the controller to evaluate paths with different costs.

### 4.3 UDP Diagnostic System

The UDP diagnostic system measures network performance between hosts.

The client sends UDP diagnostic packets to the server and calculates:
- Round Trip Time.
- Packet loss percentage.
- Average latency.
- Jitter.
- Communication status.

The measurements are transmitted to the controller's REST API.

### 4.4 Analysis Module

The analysis module processes diagnostic measurements and network information.

It provides:
- JSON data loading.
- Path and measurement correlation.
- Network failure analysis.
- Identification of degraded network conditions.

## 5. Project Directory Structure

```text
sdn-network-diagnostic-tool/
│
├── analysis/
│   ├── loader.py
│   ├── correlate.py
│   └── failures.py
│
├── data/
│   ├── baseline_S0.json
│   ├── measurements.json
│   └── topology.json
│
├── probe/
│   ├── client.py
│   └── server.py
│
├── results/
│
├── sdn/
│   ├── controller.py
│   ├── controller_dijkstra.py
│   ├── forwarding.py
│   ├── paths.py
│   ├── rest_api.py
│   └── topology_discovery.py
│
├── tests/
│
├── client.py
├── server.py
├── config.py
├── topo.py
├── requirements.txt
└── README.md

6. Installation and Setup
Prerequisites
- Ubuntu Linux.
- Python 3.
- Mininet.
- Open vSwitch.
- Ryu SDN framework.
Install Python Dependencies
Clone the repository:
git clone https://github.com/adithyaroy-38/sdn-network-diagnostic-tool.git
cd sdn-network-diagnostic-tool

Install the Python dependencies:
pip install -r requirements.txt

If using the existing Ryu virtual environment:
source ~/ryu-env/bin/activate

7. How to Run the Project
The demonstration requires three main environments:
1. Ryu controller terminal.
2. Mininet terminal.
3. Analysis terminal.
Step 1: Start the Ryu Controller
From the project directory:
ryu-manager --observe-links \
--ofp-tcp-listen-port 6653 \
--wsapi-port 8080 \
sdn/controller_dijkstra.py \
sdn/topology_discovery.py \
sdn/rest_api.py

The controller listens for OpenFlow connections on port 6653 and provides REST services on port 8080.
Step 2: Start the Mininet Topology
Open another terminal:
cd ~/sdn-network-diagnostic-tool

Start the custom diamond topology:
sudo mn --custom topo.py \
--topo diamond \
--controller=remote,ip=127.0.0.1,port=6653 \
--switch ovsk,protocols=OpenFlow13

Step 3: Verify Network Connectivity
Inside the Mininet CLI:
pingall

This verifies connectivity between the network hosts.
Step 4: Start the UDP Server
Inside Mininet:
h2 python3 server.py

The UDP server listens for incoming diagnostic packets.
Step 5: Run the UDP Diagnostic Client
Open another Mininet terminal prompt and execute:
h1 python3 client.py --src=h1 --dst=h2

The client sends diagnostic packets and calculates network performance measurements.

The client also supports selecting different source and destination hosts.
Step 6: Access the REST API
The REST API exposes network information and diagnostic reporting endpoints.

Available endpoints:
Method	Endpoint	Purpose
GET	/diag/topology	Retrieve discovered topology
GET	/diag/paths?src=h1&dst=h2	Retrieve path information
POST	/diag/report	Submit diagnostic measurements


Example:
curl http://10.0.0.254:8080/diag/topology

8. Data Analysis
The analysis module processes collected network information.

Run the JSON data loader:
python3 analysis/loader.py

Run the analysis using the live dataset:
SDN_DATASET=live python3 analysis/loader.py

Run path and measurement correlation:
SDN_DATASET=live python3 analysis/correlate.py

Run network failure analysis:
SDN_DATASET=live python3 analysis/failures.py

9. Testing and Results
The project was tested using the Mininet-emulated network.

The following scenarios were demonstrated:
Test Case 1: Network Connectivity
Objective: Verify communication between hosts.

Method: Execute pingall inside Mininet.

Expected Result: Successful connectivity between reachable hosts.
Test Case 2: Topology Discovery
Objective: Verify dynamic discovery of network switches and links.

Method: Start the Ryu controller with link observation enabled.

Expected Result: The controller discovers the network topology using LLDP.
Test Case 3: Shortest Path Calculation
Objective: Identify the optimal route between two hosts.

Method: Use the controller's Dijkstra-based path calculation.

Expected Result: The controller identifies the lower-cost route.
Test Case 4: UDP Network Diagnostics
Objective: Measure network performance.

Method: Send UDP diagnostic packets between hosts.

Measurements:
- RTT.
- Packet loss.
- Jitter.
- Average latency.
Expected Result: The client calculates and reports network performance metrics.
Test Case 5: REST API Reporting
Objective: Verify diagnostic data communication.

Method: Submit diagnostic measurements to /diag/report.

Expected Result: The REST API accepts and processes diagnostic reports.
Test Case 6: Network Failure Analysis
Objective: Identify degraded network conditions.

Method: Analyse diagnostic measurements and correlate them with network paths.

Expected Result: The analysis module identifies potential network failures and degraded performance.
10. Key Features
- SDN-based network management.
- Dynamic topology discovery using LLDP.
- Dijkstra shortest-path calculation.
- Alternative path identification.
- UDP socket-based network diagnostics.
- RTT, jitter, and packet loss measurement.
- REST API-based diagnostic reporting.
- JSON-based network data processing.
- Path and performance correlation.
- Network failure analysis.
11. Limitations
- The network is emulated using Mininet rather than deployed on physical networking hardware.
- Diagnostic results depend on the configured topology and network conditions.
- REST diagnostic reports are currently maintained in memory and are not permanently persisted by the REST service.
- Network performance measurements may vary depending on the host system and emulation environment.
12. Future Enhancements
- Persistent storage of diagnostic reports.
- Real-time network monitoring dashboard.
- Automated rerouting during network failures.
- Additional network performance metrics.
- Testing on larger and more complex topologies.
- Integration with physical SDN-enabled networking hardware.
13. Conclusion
The SDN Network Diagnostic and Path Analysis Tool demonstrates how Software-Defined Networking can be combined with UDP socket programming to monitor and analyse network performance.

By integrating Ryu, Mininet, LLDP-based topology discovery, Dijkstra path calculation, UDP diagnostics, REST API reporting, and data analysis, the project provides a framework for identifying network performance issues and evaluating communication paths.

The implementation demonstrates the practical application of SDN concepts, network programming, and network performance analysis.
