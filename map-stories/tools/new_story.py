"""Scaffold starter specs from the topics list, so an agent only fills in research, beats and places.

usage:
  python tools/new_story.py --from-csv topics/topics.csv          # one stories/<id>.json per row that has none
  python tools/new_story.py --id hannibal-218bc --title "Elephants Over the Alps" --style antique --year -218

topics.csv columns: id,title,subtitle,style,shape,hook,sources
"""
import argparse, csv, json, os

HERE = os.path.dirname(os.path.abspath(__file__))
STORIES = os.path.join(HERE, '..', 'stories')


def starter(row):
    style = row.get('style') or 'light'
    return {
        'id': row['id'],
        'title': row['title'],
        'subtitle': row.get('subtitle', ''),
        'style': style,
        'aspects': ['16:9', '9:16'],
        'fps': 30,
        'voice': {'engine': 'kokoro', 'speaker': 'am_fenrir', 'speed': 1.2,
                  'credit': 'Kokoro-82M TTS, voice am_fenrir (Apache-2.0)'},
        'music': None,
        'sfx': False,
        'captions': True,
        'map': {'borders': False, 'rivers': True, 'graticule': True},
        'places': {'TODO-place': {'name': 'TODO', 'lat': 0.0, 'lon': 0.0, 'kind': 'city'}},
        'routes': {},
        'beats': [
            {'vo': row.get('hook') or 'TODO hook line (step 2)', 'camera': {'to': [20.0, 0.0], 'zoom': 'globe', 'tilt': 0}},
            {'vo': 'TODO beat 2', 'camera': {'to': 'TODO-place', 'zoom': 'region', 'tilt': 30}, 'labels': ['TODO-place']},
            {'vo': 'TODO ending that pays off the hook', 'camera': {'to': ['TODO-place'], 'tilt': 20, 'pad': 1.5}, 'min': 5.0},
        ],
        'sources': [{'title': s.strip(), 'url': s.strip()} for s in (row.get('sources') or '').split('|') if s.strip()],
        'notes': f"shape: {row.get('shape', '')}. Fill in following PLAYBOOK.md steps 1-7, then validate.",
    }


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--from-csv'); ap.add_argument('--id'); ap.add_argument('--title'); ap.add_argument('--style', default='light')
    ap.add_argument('--force', action='store_true')
    a = ap.parse_args()
    rows = []
    if a.from_csv:
        with open(a.from_csv, encoding='utf8') as f:
            rows = list(csv.DictReader(f))
    elif a.id and a.title:
        rows = [{'id': a.id, 'title': a.title, 'style': a.style}]
    else:
        ap.error('give --from-csv or --id and --title')
    os.makedirs(STORIES, exist_ok=True)
    n = 0
    for r in rows:
        p = os.path.join(STORIES, r['id'] + '.json')
        if os.path.exists(p) and not a.force:
            continue
        with open(p, 'w', encoding='utf8') as f:
            json.dump(starter(r), f, indent=2, ensure_ascii=False)
        n += 1; print('wrote', p)
    print(n, 'starter specs')


if __name__ == '__main__':
    main()
