import logging
from uuid import uuid4

from sourced.ml.extractors import IdentifiersBagExtractor
from sourced.ml.models import OrderedDocumentFrequencies
from sourced.ml.transformers import Cacher, UastDeserializer, CooccConstructor, CooccModelSaver, \
    BagFeatures2DocFreq, Uast2BagFeatures, Counter, UastRow2Document, Repartitioner, \
    create_uast_source
from sourced.ml.utils.engine import pipeline_graph, pause


@pause
def repos2coocc_entry(args):
    log = logging.getLogger("repos2coocc")
    id_extractor = IdentifiersBagExtractor(docfreq_threshold=args.min_docfreq,
                                           split_stem=args.split)
    session_name = "repos2coocc-%s" % uuid4()
    root, start_point = create_uast_source(args, session_name)

    uast_extractor = start_point \
        .link(UastRow2Document()) \
        .link(Repartitioner.maybe(args.partitions, args.shuffle)) \
        .link(Cacher.maybe(args.persist))
    log.info("Extracting UASTs...")
    ndocs = uast_extractor.link(Counter()).execute()
    log.info("Number of documents: %d", ndocs)
    uast_extractor = uast_extractor.link(UastDeserializer())

    df = uast_extractor \
        .link(Uast2BagFeatures([id_extractor])) \
        .link(BagFeatures2DocFreq()) \
        .execute()

    log.info("Writing document frequency model to %s...", args.docfreq)
    df_model = OrderedDocumentFrequencies() \
        .construct(ndocs, df) \
        .prune(args.min_docfreq) \
        .greatest(args.vocabulary_size) \
        .save(args.docfreq)

    token2index = root.session.sparkContext.broadcast(df_model.order)
    uast_extractor \
        .link(CooccConstructor(token2index=token2index,
                               token_parser=id_extractor.id2bag.token_parser,
                               namespace=id_extractor.NAMESPACE)) \
        .link(CooccModelSaver(args.output, df_model)) \
        .execute()
    pipeline_graph(args, log, root)
