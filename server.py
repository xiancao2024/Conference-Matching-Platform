from conference_matching.server import build_parser, run


if __name__ == "__main__":
    args = build_parser().parse_args()
    run(host=args.host, port=args.port)
