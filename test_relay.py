import asyncio
import websockets

async def test_flow():
    relay_ip = "54.242.81.228"
    port = 80
    
    print(f"Connecting to ws://{relay_ip}:{port}/register as Host...")
    try:
        host_ws = await websockets.connect(f"ws://{relay_ip}:{port}/register")
        msg = await host_ws.recv()
        print(f"Host received: {msg}")
        
        if msg != "ID=123456":
            print(f"Warning: Expected ID=123456, got: {msg}")
            
        print(f"Connecting to ws://{relay_ip}:{port}/join/123456 as Client...")
        client_ws = await websockets.connect(f"ws://{relay_ip}:{port}/join/123456")
        
        client_msg = await client_ws.recv()
        print(f"Client received: {client_msg}")
        
        host_msg = await host_ws.recv()
        print(f"Host received after client connect: {host_msg}")
        
        print("Sending message from Client to Host...")
        await client_ws.send("Hello from Client")
        
        received_at_host = await host_ws.recv()
        print(f"Host received message: {received_at_host}")
        
        print("Sending message from Host to Client...")
        await host_ws.send("Hello from Host")
        
        received_at_client = await client_ws.recv()
        print(f"Client received message: {received_at_client}")
        
        print("Closing connections...")
        await host_ws.close()
        await client_ws.close()
        print("Test successful!")
        
    except Exception as e:
        print(f"Test failed with error: {e}")

if __name__ == "__main__":
    asyncio.run(test_flow())
