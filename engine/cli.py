import argparse
import json
from pathlib import Path
from .models import Brief, Review
from .service import Engine
from .store import Store


def main():
    parser = argparse.ArgumentParser(description="Website Production Engine — independent of Studio")
    parser.add_argument("--data-dir", default=None)
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("list")
    create = sub.add_parser("create"); create.add_argument("brief")
    for name in ["show", "discover", "produce", "repair", "recover", "resume", "approve-final"]:
        operation = sub.add_parser(name); operation.add_argument("project_id")
        if name == "approve-final": operation.add_argument("build_id")
    review = sub.add_parser("review"); review.add_argument("project_id"); review.add_argument("--action", choices=["KEEP", "REVISE", "REJECT"], required=True); review.add_argument("--version", type=int, required=True); review.add_argument("--feedback", default=""); review.add_argument("--patches", default="{}")
    seed = sub.add_parser("seed"); seed.add_argument("--all-stages", action="store_true")
    args = parser.parse_args()
    engine = Engine(Store(args.data_dir))
    try:
        if args.command == "list": result = engine.store.list()
        elif args.command == "create": result = engine.create(Brief.model_validate_json(Path(args.brief).read_text()))
        elif args.command == "show": result = engine.contextual(engine.store.get(args.project_id))
        elif args.command == "review": result = engine.review(args.project_id, Review(action=args.action, version=args.version, feedback=args.feedback, patches=json.loads(args.patches)))
        elif args.command == "approve-final": result = engine.final_approve(args.project_id, args.build_id)
        elif args.command == "seed":
            from .fixtures import seed
            result = seed(engine, args.all_stages)
        else: result = getattr(engine, args.command)(args.project_id)
        print(json.dumps(result, indent=2))
    finally: engine.pool.shutdown(wait=True)


if __name__ == "__main__": main()
