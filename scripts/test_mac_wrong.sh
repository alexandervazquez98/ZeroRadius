#!/bin/sh
echo 'User-Name="mac_user1", User-Password="Secret123!", Calling-Station-Id="11:22:33:44:55:66"' | radclient 127.0.0.1:1812 auth testing1230000000000000000000000 -x
