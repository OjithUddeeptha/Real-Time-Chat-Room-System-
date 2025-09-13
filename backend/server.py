
import asyncio
import json
from collections import defaultdict, deque
from datetime import datetime
import websockets
from websockets.exceptions import ConnectionClosedOK, ConnectionClosedError

# In-memory data structures
ROOMS = defaultdict(set)                     # room_name -> set of websocket connections
USERNAMES = {}                               # websocket -> username
USER_ROOMS = {}                              # websocket -> room_name
LAST_MESSAGES = defaultdict(lambda: deque(maxlen=5))  # room_name -> deque of last messages


async def _safe_send(ws, message):
    """Send a message safely; return False if sending failed."""
    try:
        await ws.send(message)
        return True
    except Exception:
        return False


async def broadcast(room, message):
    """Broadcast a message (stringified JSON) to all clients in a room."""
    websockets_copy = list(ROOMS.get(room, []))
    if not websockets_copy:
        return
    coros = [_safe_send(ws, message) for ws in websockets_copy]
    results = await asyncio.gather(*coros)
    # Optionally prune disconnected sockets
    for ws, ok in zip(websockets_copy, results):
        if not ok:
            await unregister(ws)


async def register(ws, username, room):
    USERNAMES[ws] = username
    USER_ROOMS[ws] = room
    ROOMS[room].add(ws)


async def unregister(ws):
    room = USER_ROOMS.get(ws)
    username = USERNAMES.get(ws)
    if room and ws in ROOMS[room]:
        ROOMS[room].remove(ws)
    USER_ROOMS.pop(ws, None)
    USERNAMES.pop(ws, None)
    if username and room:
        # Notify remaining clients in the room
        leave_msg = json.dumps({
            "type": "system",
            "text": f"{username} has left the room.",
            "timestamp": datetime.utcnow().isoformat() + "Z"
        })
        await broadcast(room, leave_msg)


async def handler(ws, path):
    try:
        async for raw in ws:
            try:
                data = json.loads(raw)
            except json.JSONDecodeError:
                await ws.send(json.dumps({"type": "error", "text": "Invalid JSON"}))
                continue

            typ = data.get("type")
            if typ == "join":
                username = data.get("username", "Anonymous")
                room = data.get("room", "lobby")
                await register(ws, username, room)
                # Send history
                history = list(LAST_MESSAGES[room])
                await ws.send(json.dumps({"type": "history", "messages": history}))
                # Notify room about join
                join_msg = json.dumps({
                    "type": "system",
                    "text": f"{username} has joined the room.",
                    "timestamp": datetime.utcnow().isoformat() + "Z"
                })
                await broadcast(room, join_msg)

            elif typ == "message":
                room = USER_ROOMS.get(ws)
                username = USERNAMES.get(ws, "Anonymous")
                content = data.get("content", "")
                if room:
                    msg = {
                        "type": "message",
                        "username": username,
                        "content": content,
                        "timestamp": datetime.utcnow().isoformat() + "Z"
                    }
                    LAST_MESSAGES[room].append(msg)
                    await broadcast(room, json.dumps(msg))

            elif typ == "list_rooms":
                rooms = [r for r, s in ROOMS.items() if s]
                await ws.send(json.dumps({"type": "rooms", "rooms": rooms}))

            else:
                await ws.send(json.dumps({"type": "error", "text": "Unknown message type"}))

    except (ConnectionClosedOK, ConnectionClosedError):
        pass
    finally:
        if ws in USERNAMES or ws in USER_ROOMS:
            await unregister(ws)


async def main():
    host = "0.0.0.0"
    port = 6789
    print(f"Starting WebSocket server on ws://{host}:{port}")
    async with websockets.serve(handler, host, port):
        await asyncio.Future()  # run forever


if __name__ == "__main__":
    asyncio.run(main())
