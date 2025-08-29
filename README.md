# SLDO Test Agent

## Set up the Agent

Start docker on your compter

KAFKA_LOCAL_PORT=<Add_the_port_prefered:default-9095> docker compose up -d

-9093 cannot be used: Kafka UI is using that to access the container

!If needed to clean the containers, will lost all messages logged into the broker!. 

docker compose down -v 


## Create Topics

cd ExternalDummies

KAFKA_LOCAL_PORT=<Add_the_port_prefered:default-9095> python3 TopicCreation.py config.py

*the config.py will remember this port until you call KAFKA_LOCAL_PORT again with a different port.*

## Send messages

add the message with the right format to the test_message.json inside ExternalDummies

and

cd ExternalDummies
python3 send_request.py ../config.py test_message.json

## Running test agent

python3 -m test_agent config.py

**add different config.py if needed for the different configrations needed. Make sure to match the KAFKA_LOCAL_PORT**


## Running in local mode to test without getting kafka broker involved (local mode)

python3 -m test_agent_dev config.py --local --json ExternalDummies/test_message.json