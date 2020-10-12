@echo off
pip3 install -r requirements.txt
pip uninstall python-magic
pip install python-magic-bin~=0.4.14
pause
