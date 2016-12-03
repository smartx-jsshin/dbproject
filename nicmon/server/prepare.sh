#!/bin/bash

sudo apt-get update
sudo apt-get install -y python-pip libmysqlclient-dev python-dev
pip install -r requirements.txt