"""
Vision-based navigation agent for Spot robot using qwen3-vl model.
Uses MCP tools to control the robot and get camera input.
"""

import asyncio
import json
from typing import Any, Dict


async def navigate_robot():
    """Main navigation loop using MCP tools for forward movement with obstacle avoidance."""
    print("🤖 Starting Spot Robot Vision Navigation Agent")
    print("=" * 50)
    
    # Import MCP client
    try:
        from mcp.client.sse import sse_client
        from mcp import ClientSession
    except ImportError as e:
        print(f"❌ Failed to import MCP client: {e}")
        print("Install MCP SDK with: pip install mcp")
        return
    
    # Connect to MCP server
    print("🔗 Connecting to MCP server...")
    try:
        async with sse_client("http://127.0.0.1:8000/sse") as streams:
            async with ClientSession(streams[0], streams[1]) as session:
                await session.initialize()
                print("✅ Connected to MCP server")
                
                step = 0
                max_steps = 100
                distance_moved = 0.0
                consecutive_stops = 0

                while step < max_steps:
                    step += 1
                    print(f"\n=== Navigation Step {step} ===")

                    # Get camera image
                    print("📸 Capturing camera image...")
                    try:
                        result = await session.call_tool("getCameraImage")
                        if not result.content or not result.content[0].text:
                            print("⚠️  No camera image available")
                            await asyncio.sleep(1)
                            continue
                        
                        image_data = json.loads(result.content[0].text)
                        if not image_data.get("ok"):
                            print(f"⚠️  Camera error: {image_data.get('error')}")
                            await asyncio.sleep(1)
                            continue
                    except Exception as e:
                        print(f"⚠️  Error getting camera: {e}")
                        await asyncio.sleep(1)
                        continue

                    # Get robot state
                    print("📍 Getting robot state...")
                    try:
                        result = await session.call_tool("getState")
                        state_data = json.loads(result.content[0].text)
                        if state_data.get("spot"):
                            pose = state_data["spot"]
                            position = pose.get("position", [0, 0, 0])
                            yaw = pose.get("orientation_yaw_rad", 0)
                            print(f"   Position: X={position[0]:.2f}, Y={position[1]:.2f}, Z={position[2]:.2f}")
                            print(f"   Yaw: {yaw:.2f} rad ({yaw*180/3.14159:.1f}°)")
                    except Exception as e:
                        print(f"⚠️  Error getting state: {e}")

                    # Query vision model for navigation decision
                    print("🤖 Analyzing camera with vision model...")
                    prompt = """You are a robot navigation assistant. Analyze the camera view and respond with ONLY one of these:
- FORWARD: if the path ahead is completely clear and safe to move
- SLOW: if there are potential obstacles or you need to be cautious
- OBSTACLE_LEFT: if there's an obstacle ahead but left side looks clear
- OBSTACLE_RIGHT: if there's an obstacle ahead but right side looks clear
- BLOCKED: if the path is completely blocked in all directions

Then briefly explain what you see."""
                    
                    try:
                        result = await session.call_tool("queryVisionModel", {
                            "prompt": prompt,
                            "model": "qwen3-vl:4b"
                        })
                        vision_data = json.loads(result.content[0].text)
                        if not vision_data.get("ok"):
                            print(f"⚠️  Vision model error: {vision_data.get('error')}")
                            await asyncio.sleep(1)
                            continue
                        
                        vision_analysis = vision_data.get("response", "")
                        if vision_analysis:
                            print(f"Vision Analysis:\n{vision_analysis}")
                        else:
                            print("⚠️  Vision model did not respond")
                            await asyncio.sleep(1)
                            continue
                    except Exception as e:
                        print(f"⚠️  Error querying vision model: {e}")
                        await asyncio.sleep(1)
                        continue

                    # Parse vision analysis to decide movement
                    analysis_upper = vision_analysis.upper()
                    # Get the primary command (first word/line) to avoid matching words in explanation
                    primary_command = analysis_upper.split('\n')[0]
                    
                    movement_command = None
                    speed = 0.5
                    duration = 1.0
                    
                    if "FORWARD" in primary_command:
                        print("🚀 Moving forward...")
                        movement_command = "forward"
                        speed = 1.0
                        duration = 2.0
                        consecutive_stops = 0
                        
                    elif "SLOW" in primary_command:
                        print("🚀 Moving forward slowly...")
                        movement_command = "forward"
                        speed = 1.0
                        duration = 1.0
                        consecutive_stops = 0
                        
                    elif "OBSTACLE_LEFT" in primary_command:
                        print("↙️  Obstacle ahead, trying to move left...")
                        movement_command = "left"
                        speed = 1.0
                        duration = 1.0
                        consecutive_stops = 0
                        
                    elif "OBSTACLE_RIGHT" in primary_command:
                        print("↘️  Obstacle ahead, trying to move right...")
                        movement_command = "right"
                        speed = 1.0
                        duration = 1.0
                        consecutive_stops = 0
                        
                    elif "BLOCKED" in primary_command:
                        consecutive_stops += 1
                        print(f"🛑 Path blocked - attempting to find alternative (attempt {consecutive_stops})")
                        
                        # Try rotating to find a way around
                        if consecutive_stops <= 2:
                            print("↪️  Rotating to find alternative path...")
                            movement_command = "turn_left"
                            speed = 1.0
                            duration = 1.0
                        elif consecutive_stops <= 4:
                            print("↩️  Rotating the other way...")
                            movement_command = "turn_right"
                            speed = 1.0
                            duration = 1.0
                        else:
                            print("❌ Unable to find path around obstacle after multiple attempts")
                            try:
                                await session.call_tool("stop")
                                print("✅ Robot stopped")
                            except Exception as e:
                                print(f"Error stopping: {e}")
                            await asyncio.sleep(2)
                            break
                    else:
                        # Default: try moving forward cautiously
                        print("⚠️  Uncertain path, moving forward slowly...")
                        movement_command = "forward"
                        speed = 1.0
                        duration = 1.0
                        consecutive_stops = 0

                    # Send movement command
                    if movement_command:
                        try:
                            result = await session.call_tool("giveMoveCommand", {
                                "direction": movement_command,
                                "length": duration,
                                "speed": speed,
                                "yaw_rate": 0.8
                            })
                            cmd_data = json.loads(result.content[0].text)
                            if cmd_data.get("ok"):
                                applied = cmd_data.get("applied", {})
                                # Track distance only for forward movements
                                if movement_command == "forward":
                                    distance_moved += applied.get("duration_s", 0) * speed
                                print(f"✅ Move command sent (direction={movement_command}, speed={speed} m/s, duration={duration}s)")
                                print(f"   Total forward distance: {distance_moved:.2f}m")
                            else:
                                print(f"⚠️  Move command failed: {cmd_data}")
                        except Exception as e:
                            print(f"Error sending move command: {e}")

                        await asyncio.sleep(1)

                print("\n" + "=" * 50)
                print("🎯 Navigation Complete")
                print(f"Total steps: {step}")
                print(f"Total forward distance moved: {distance_moved:.2f}m")
    
    except Exception as e:
        print(f"❌ Failed to connect to MCP server: {e}")
        print("Make sure the main.py simulation is running with MCP server enabled")
        return


if __name__ == "__main__":
    asyncio.run(navigate_robot())
