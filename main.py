import argparse
from app.db import init_db
from app.ingestion import ingest_from_source
from app.segmentation import segment_book
from app.generation import generate_for_chapter
from app.verification import verify_item, edit_item, chapter_progress
from app.export import export_book

def main():
    parser = argparse.ArgumentParser()
    sub = parser.add_subparsers(dest="cmd")

    sub.add_parser("init-db")

    p_ingest = sub.add_parser("ingest")
    p_ingest.add_argument("--source", required=True)

    p_segment = sub.add_parser("segment")
    p_segment.add_argument("--book-id", type=int, required=True)
    p_segment.add_argument("--max-tokens", type=int, default=1000)

    p_generate = sub.add_parser("generate")
    p_generate.add_argument("--chapter-id", type=int, required=True)
    p_generate.add_argument("--count", type=int, default=5)
    p_generate.add_argument("--type", choices=["qa","exercise"], default="qa")
    p_generate.add_argument("--model", default="mock")

    p_verify = sub.add_parser("verify")
    p_verify.add_argument("--item-id", type=int, required=True)

    p_edit = sub.add_parser("edit")
    p_edit.add_argument("--item-id", type=int, required=True)
    p_edit.add_argument("--question", required=False)
    p_edit.add_argument("--options", required=False)
    p_edit.add_argument("--answer", required=False)
    p_edit.add_argument("--explanation", required=False)

    p_progress = sub.add_parser("progress")
    p_progress.add_argument("--chapter-id", type=int, required=True)

    p_export = sub.add_parser("export")
    p_export.add_argument("--book-id", type=int, required=True)
    p_export.add_argument("--out", required=True)

    args = parser.parse_args()
    if args.cmd == "init-db":
        init_db()
        print("db initialized")
    elif args.cmd == "ingest":
        book_id = ingest_from_source(args.source)
        print(f"ingested book {book_id}")
    elif args.cmd == "segment":
        segment_book(args.book_id, args.max_tokens)
        print("segmentation done")
    elif args.cmd == "generate":
        generate_for_chapter(args.chapter_id, args.count, args.type, args.model)
        print("generation done")
    elif args.cmd == "verify":
        verify_item(args.item_id)
        print("verified")
    elif args.cmd == "edit":
        edit_item(args.item_id, args.question, args.options, args.answer, args.explanation)
        print("edited")
    elif args.cmd == "progress":
        p = chapter_progress(args.chapter_id)
        print(f"chapter {args.chapter_id} verified {int(p*100)}%")
    elif args.cmd == "export":
        export_book(args.book_id, args.out)
        print("exported")
    else:
        parser.print_help()

if __name__ == "__main__":
    main()