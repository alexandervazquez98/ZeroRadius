#!/bin/sh
echo 'User-Name="mac_user1", User-Password="Secret123!", Calling-Station-Id="AA:BB:CC:DD:EE:FF"' | radclient 127.0.0.1:1812 auth testing1230000000000000000000000 -x
