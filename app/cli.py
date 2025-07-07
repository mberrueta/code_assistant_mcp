# app/cli.py
import argparse
from app.database import add_file_to_db, get_all_records, remove_file_from_db, query_db
import json

def main():
    parser = argparse.ArgumentParser(description="A CLI tool for interacting with a ChromaDB database.")
    subparsers = parser.add_subparsers(dest="command", help="Available commands.")

    # 'add' command
    add_parser = subparsers.add_parser("add", help="Add a file to the database.")
    add_parser.add_argument("file_path", type=str, help="The path to the file to add.")

    # 'view' command
    subparsers.add_parser("view", help="View all records in the database.")

    # 'remove' command
    remove_parser = subparsers.add_parser("remove", help="Remove a file from the database.")
    remove_parser.add_argument("file_path", type=str, help="The path to the file to remove.")

    # 'query' command
    query_parser = subparsers.add_parser("query", help="Query the database for relevant documents.")
    query_parser.add_argument("query_text", type=str, help="The text to query the database with.")
    query_parser.add_argument("--n_results", type=int, default=2, help="Number of results to return.")

    args = parser.parse_args()

    if args.command == "add":
        result = add_file_to_db(args.file_path)
        print(result)
    elif args.command == "view":
        records = get_all_records()
        print(json.dumps(records, indent=2))
    elif args.command == "remove":
        confirm = input(f"Are you sure you want to remove {args.file_path} from the database? (yes/no): ")
        if confirm.lower() == 'yes':
            result = remove_file_from_db(args.file_path)
            print(result)
        else:
            print("Removal cancelled.")
    elif args.command == "query":
        results = query_db(args.query_text, args.n_results)
        print(json.dumps(results, indent=2))
    else:
        parser.print_help()

if __name__ == "__main__":
    main()
