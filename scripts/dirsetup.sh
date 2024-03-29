#!/bin/bash

# =================================================================
# Set up condor output directory for I/O to condor directory
# =================================================================
print_env_variable() { var="$1"; [ -z "${!var}" ] && echo "$var is not set" || echo "$var has been set to ${!var}"; }

export IS_CONDOR=true
print_env_variable "IS_CONDOR"

source scripts/lpcsetup.sh

# if receiving arguments <datasetname>
# check if condor directory exists
if [ ! -z "$1" ]; then
    DIRNAME=$SHORTPATH/$1
else
    DIRNAME=$SHORTPATH/all
fi

if xrdfs $PREFIX stat $DIRNAME >/dev/null 2>&1; then
    echo "the directory $DIRNAME already exists"
else
    echo "creating directory $DIRNAME."
    xrdfs $PREFIX mkdir -p $DIRNAME
fi

echo "CONDOR outputpath will be $DIRNAME"
