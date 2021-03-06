import logging
from uuid import uuid4

from sourced.ml.transformers import ContentToIdentifiers, create_uast_source, LanguageSelector, \
    IdentifiersToDataset, CsvSaver, Repartitioner
from sourced.ml.utils.engine import pipeline_graph, pause


@pause
def repos2ids_entry(args):
    log = logging.getLogger("repos2ids")
    session_name = "repos2ids-%s" % uuid4()
    language_selector = LanguageSelector(languages=["null"], blacklist=True)
    root, start_point = create_uast_source(args, session_name, language_selector=language_selector,
                                           extract_uast=False)
    start_point \
        .link(Repartitioner(args.partitions, args.shuffle)) \
        .link(ContentToIdentifiers(args.split)) \
        .link(IdentifiersToDataset(args.idfreq)) \
        .link(CsvSaver(args.output)) \
        .execute()
    pipeline_graph(args, log, root)
