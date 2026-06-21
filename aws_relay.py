import asyncio
import websockets
import random
import logging
import sys

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("RelayServer")

# Session registry: maps 6-digit ID -> { "host": websocket, "client": websocket }
sessions = {}

async def register_host(websocket):
    # Use fixed 6-digit ID and override any existing session
    session_id = "123456"
    if session_id in sessions:
        logger.info(f"Session ID {session_id} already exists. Disconnecting the old host and client.")
        old_session = sessions.pop(session_id, None)
        if old_session:
            if old_session["host"]:
                try:
                    await old_session["host"].close()
                except Exception:
                    pass
            if old_session["client"]:
                try:
                    await old_session["client"].send("HOST_DISCONNECTED")
                    await old_session["client"].close()
                except Exception:
                    pass
            
    sessions[session_id] = {
        "host": websocket,
        "client": None
    }
    logger.info(f"Host registered. Session ID: {session_id}")
    
    try:
        # Send the generated ID to the host
        await websocket.send(f"ID={session_id}")
        
        # Loop to receive from Host and relay to Client
        async for message in websocket:
            session = sessions.get(session_id)
            if session and session["client"]:
                # Relay binary screen frames (or control text messages)
                try:
                    await session["client"].send(message)
                except Exception as e:
                    logger.error(f"Error relaying from host to client in {session_id}: {e}")
            else:
                # Buffer or ignore if no client joined
                pass
    except websockets.exceptions.ConnectionClosed:
        logger.info(f"Host connection closed for session {session_id}")
    finally:
        # Host disconnected, clean up
        session = sessions.pop(session_id, None)
        if session and session["client"]:
            try:
                await session["client"].send("HOST_DISCONNECTED")
                await session["client"].close()
            except Exception:
                pass
        logger.info(f"Session {session_id} cleaned up")

async def join_client(websocket, session_id):
    if session_id not in sessions:
        logger.warning(f"Join rejected. Session {session_id} not found.")
        await websocket.send("ERROR: ID_NOT_FOUND")
        await websocket.close()
        return
        
    session = sessions[session_id]
    if session["client"] is not None:
        logger.warning(f"Join rejected. Session {session_id} already has client.")
        await websocket.send("ERROR: SESSION_BUSY")
        await websocket.close()
        return
        
    session["client"] = websocket
    logger.info(f"Client joined session {session_id}")
    
    try:
        # Notify both parties of successful connection
        await websocket.send("CONNECTED")
        await session["host"].send("CLIENT_CONNECTED")
        
        # Loop to receive from Client (touch/keyboard commands) and relay to Host
        async for message in websocket:
            # Relay commands (always text)
            try:
                await session["host"].send(message)
            except Exception as e:
                logger.error(f"Error relaying from client to host in {session_id}: {e}")
    except websockets.exceptions.ConnectionClosed:
        logger.info(f"Client connection closed for session {session_id}")
    finally:
        # Client disconnected
        if session_id in sessions:
            sessions[session_id]["client"] = None
            try:
                await sessions[session_id]["host"].send("CLIENT_DISCONNECTED")
            except Exception:
                pass
        logger.info(f"Client removed from session {session_id}")

async def handler(websocket, path=None):
    # Support websockets v8/v9 (passes path), v10/v11 (websocket.path), and v12+ (websocket.request.path)
    if path is None:
        if hasattr(websocket, "path"):
            path = websocket.path
        elif hasattr(websocket, "request") and hasattr(websocket.request, "path"):
            path = websocket.request.path
        else:
            path = "/register"
        
    logger.info(f"New connection request on path: {path}")
    if path == "/register":
        await register_host(websocket)
    elif path.startswith("/join/"):
        session_id = path.split("/")[-1].strip()
        await join_client(websocket, session_id)
    else:
        logger.warning(f"Unknown path: {path}")
        await websocket.close()

async def main():
    port = 80
    if len(sys.argv) > 1:
        try:
            port = int(sys.argv[1])
        except ValueError:
            logger.warning(f"Invalid port value: {sys.argv[1]}. Using default port 80.")
            port = 80

    logger.info(f"Starting AWS Relay Server on 0.0.0.0:{port}...")
    server = await websockets.serve(
        handler,
        "0.0.0.0",
        port,
        max_size=80 * 1024 * 1024,
        ping_interval=30,
        ping_timeout=60
    )
    await server.wait_closed()

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Server stopped by user.")
