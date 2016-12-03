#!/bin/bash

sudo apt-get update
sudo apt-get install python-pip libmysqlclient-dev python-dev
pip install -e requirements.txt