# SLDO Test Agent

## Set up the Agent

Start docker on your compter

Refer to README.md in cd Dev/Kafka to start the kafka broker

## Create Topics

cd ExternalDummies

python3 TopicCreation.py config.py

## Send messages

add the message with the right format to the test_message.json inside ExternalDummies

and

cd ExternalDummies
python3 send_request.py ../config.py test_message.json

## Running test agent

python3 -m test_agent config.py

-> add the config.py needed for the configrations needed. 


## Running in local mode to test without getting kafka broker involved (local mode)

python3 -m test_agent config.py --local --json ExternalDummies/test_message.json