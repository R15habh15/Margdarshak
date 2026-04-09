import sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from src.osm_pipeline.traffic_generator import generate_routes

nets_dir = os.path.join('data', 'sumo_networks')
nets = [f for f in os.listdir(nets_dir) if f.endswith('.net.xml')]
print('Networks found:', nets)

for net in nets:
    print(f'Regenerating {net} ...')
    try:
        r = generate_routes(net)
        print('  config:', r['config'])
    except Exception as e:
        print('  ERROR:', e)

print('Done.')
