#!/usr/bin/env bash
# Fail closed: the historical entrypoint mutates shared Nginx.
echo 'Retired shared-proxy deployment. Use the reviewed deploy/production release pipeline after approved ingress cutover.' >&2
exit 1
