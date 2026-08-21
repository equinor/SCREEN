#!/bin/bash
uname -a
date

# TODO(hzh): tell where python is located
PYTHON_HOME="/home/hzh/equinor/screen/SCREEN/venv_SCREEN/bin"

# run the following script from project directory
#
# Usage:
#
#   ./runscripts/run_well_sketch.sh --config_file ./test_data/examples/smeaheia/smeaheia.yaml --out_name t.jpeg

# where to launch the current shell script
LAUNCH_DIR=${PWD}
echo "Running python job from: ${PWD}"

# find out where the executable is
BASEDIR=$(dirname $0)
# running directory (absolute path)
RUNNING_DIR="$(cd $BASEDIR/..; pwd)"

# switch to running directory
echo "===> switch to project directory ${RUNNING_DIR}"
cd ${RUNNING_DIR}

# executable
EXECUTABLE=" -m experiments.well_sketch"

# data root directory
CONFIG_FILE=

# set default output path to the launching directory
OUT_PATH=" --out-path ${LAUNCH_DIR}"

# user id
OUT_NAME=

# no display
NO_DISPLAY=

# analyze commandline arguments
while [[ "$#" -gt 0 ]]; do
    case $1 in
        -c|--config_file) CONFIG_FILE=" --config-file $2"; shift ;;
        -p|--out_path) OUT_PATH=" --out-path $2"; shift ;;
        -o|--out_name) OUT_NAME=" --out-name $2"; shift ;;
        -n|--nodisplay) NO_DISPLAY=" --nodisplay";;
        *) echo "Unknown parameter passed: $1"; exit 1 ;;
    esac
    shift
done

# show commandline
echo ${PYTHON_HOME}/python  \
   ${EXECUTABLE} \
   ${CONFIG_FILE} ${OUT_PATH} ${OUT_NAME} ${NO_DISPLAY}

# actually run it
${PYTHON_HOME}/python  \
   ${EXECUTABLE} \
   ${CONFIG_FILE} ${OUT_PATH} ${OUT_NAME} ${NO_DISPLAY}

# back to original directory
echo "===> switch back to launching directory ${LAUNCH_DIR}"
cd ${LAUNCH_DIR}
