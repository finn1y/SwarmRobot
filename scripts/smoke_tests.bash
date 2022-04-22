#!/usr/bin/env bash

#script to test swarm robot system with multiple simulated agents
#these tests do not ensure that the system will perform as designed just that they 
#will run without errors

#----------------------------------------------------------------------------------------
# Set up script
#----------------------------------------------------------------------------------------

#do not exit on error
set +e

#ensure script is executed from root
cd "$(dirname $0)/../"

#----------------------------------------------------------------------------------------
# Global variables
#----------------------------------------------------------------------------------------

#init number of failed tests
FAILS=0

#----------------------------------------------------------------------------------------
# main
#----------------------------------------------------------------------------------------

#make logs dir if doesn't exist
if [ ! -d logs/ ]; then
    mkdir -p logs/
fi

#make smoke log file if doesn't exist
if [ ! -f logs/smoke_master_logs.txt ]; then
    touch logs/smoke_master_logs.txt
fi

#make smoke log file if doesn't exist
if [ ! -f logs/smoke_agent_logs.txt ]; then
    touch logs/smoke_agent_logs.txt
fi

#clear log contents
: > logs/smoke_master_logs.txt
: > logs/smoke_agent_logs.txt

echo -e "Running master...\n./master/master.py -vv --simulation\n" | tee -a logs/smoke_master_logs.txt
./master/master.py -vv --simulation >> logs/smoke_master_logs.txt 2>&1 &

#sleep before starting agent simulation
sleep 5

echo -e "Running agent simulation...\n./py_agent/agent.py -vv -a 2\n" | tee -a logs/smoke_agent_logs.txt
./py_agent/env_wrapper.py -vv -a 2 >> logs/smoke_agent_logs.txt 2>&1 &

#sleep before checking for pass
sleep 30

#check logs for required functionality

#master must add 2 agents and receive 2 rewards from each agent
MASTER_PASS=$(grep -cE 'Agent added|/agents/0/reward|/agents/1/reward' "logs/smoke_master_logs.txt")
#agents must receive an index and receive 2 actions from master
AGENT1_PASS=$(grep -cE 'Agent index: 0|/agents/0/action' "logs/smoke_agent_logs.txt")
AGENT2_PASS=$(grep -cE 'Agent index: 1|/agents/1/action' "logs/smoke_agent_logs.txt")

#check if number of tests passed meets required for each
if [ $MASTER_PASS -gt 6 ]; then
    echo -e "Master test passed"
else
    FAILS=$((FAILS+1))
    echo -e "Master test failed"
fi

if [ $AGENT1_PASS -gt 3 ]; then
    echo -e "Agent 1 test passed"
else
    FAILS=$((FAILS+1))
    echo -e "Agent 1 test failed"
fi

if [ $AGENT2_PASS -gt 3 ]; then
    echo -e "Agent 2 test passed"
else
    FAILS=$((FAILS+1))
    echo -e "Agent 2 test failed"
fi

#print out number of failed tests and list of which tests failed
echo "Smoke tests completed with ${FAILS} failed tests"

#kill all python processes (master and agents)
pkill -SIGKILL python3

exit 0



