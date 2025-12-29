# Controlling robots using Multimodal LLMs

The goal is to create a robot that is able to navigate through some challenges. I am using a pretrained model for the Spot robot. The higher level direction commands should come from an agent. The agent will be able to query an MCP server that will give the state of the robot and will be able to send commands to the robot.

![Demo](media/demo.gif)

The top view shows the environment and the lower part shows the view from the robot. (Video shows manual control, agent mode is working, but not as nice yet ^^)

## Project Structure

The project has been refactored into a modular structure:

- `main.py`: Entry point for the application.
- `agent.py`: The autonomous agent that controls the robot via MCP.
- `src/`: Source code directory.
    - `config.py`: Configuration settings (ports, assets, etc.).
    - `simulation.py`: Handles the Isaac Sim environment and robot.
    - `bridge.py`: Shared state bridge between simulation and servers.
    - `mcp_server.py`: FastMCP server implementation.
    - `http_server.py`: Debug HTTP server implementation.

## Usage

### 1. Start the Simulation and MCP Server

This starts Isaac Sim with the embedded MCP server.

```bash
./run.sh
# OR
python main.py
```

Options:
- `--mcp-disable`: Disable the MCP server.
- `--debug-http-port <port>`: Port for the debug HTTP server (default: 8001).

### 2. Run the Agent

Once the simulation is running, you can run the agent in a separate terminal:

```bash
python agent.py
```

The agent will connect to the MCP server, analyze the camera feed using the Ollama vision model, and control the robot.

### 3. Debugging

**Browser Check (Easy Mode)**

For quick manual checks, you can use the debug HTTP endpoint:

- Open `http://127.0.0.1:8001/state` to see the robot's state.
- Open `http://127.0.0.1:8001/camera` to see the current camera view.
- Trigger movement: `http://127.0.0.1:8001/move?direction=forward&length=1.0`
- Stop: `http://127.0.0.1:8001/stop`


## Current Issues
- Spot rotates after placement since the controll does not try to keep the heading. This leads to error that accumulate quite fast -> need another bot, for example the nvidia turtlebot
- Processing of the camera state by the agent takes quite a long time. Find ways to speed this up, either by outsourcing to cloud or using a different model

## Requirements

- Isaac Sim
- Python 3.10+
- `mcp` package (`pip install mcp`)
- `ollama` with `qwen3-vl:4b` model (for the agent)
