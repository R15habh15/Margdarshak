import asyncio
import websockets
import json

async def test():
    try:
        async with websockets.connect('ws://127.0.0.1:8000/api/simulation/stream') as ws:
            msg = await ws.recv()
            data = json.loads(msg)
            print('Keys:', data.keys())
            print('Vehicles sample:', data.get('vehicles', [])[:2])
            if 'error' in data: print('Error:', data['error'])
    except Exception as e:
        print("Exception:", e)

asyncio.run(test())
