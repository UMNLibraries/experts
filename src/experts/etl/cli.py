import dotenv_switch.auto

import os
import sys

import click

from loguru import logger
logger.remove()

# args & params for logger.add():
logger_args = [] # Should contain only one value, the sink.
logger_params = {
    'level':       os.environ.get('EXPERTS_ETL_LOG_LEVEL', 'INFO'),
    'serialize':   os.environ.get('EXPERTS_ETL_LOG_SERIALIZE', False),
}

# python-dotenv evaluates any string as True in a boolean context, so we do the following instead.
if isinstance(logger_params['serialize'], str):
    logger_params['serialize'] = logger_params['serialize'].lower()
# Note: Some of the values we test against here may never occur, given preceding code,
# but we test for them anyway, just to be cautious and document intent:
if logger_params['serialize'] in (0, '0', 'false', '', 'none', None):
    logger_params['serialize'] = False

if (log_file := os.environ.get('EXPERTS_ETL_LOG_FILE', None)):
    logger_args.append(log_file)
    # These values can be passed to logger.add only if the sink is a file:
    logger_params.update({
        'rotation':    os.environ.get('EXPERTS_ETL_LOG_ROTATION', '1 month'),
        'retention':   os.environ.get('EXPERTS_ETL_LOG_RETENTION', '1 year'),
        'compression': os.environ.get('EXPERTS_ETL_LOG_COMPRESSION', 'gz'),
    })

if len(logger_args) == 0:
    logger_args.append(sys.stderr)

logger.add(
    *logger_args,
    **logger_params,
)

@click.group()
# This didn't work!
#@click.option('--log-file', 'log_sink', type=str, default=sys.stderr)
#def etl(log_sink):
def etl():
    pass

@etl.command()
def pure():
    logger.info('Starting pure...')
    from experts.etl import pure

@etl.command()
@click.option('--all', '_all', is_flag=True)
@click.option('--abstracts', is_flag=True)
@click.option('--citations', is_flag=True)
def scopus(_all, abstracts, citations):
    logger.info('Starting scopus...')
    if _all:
        abstracts = True
        citations = True
    if abstracts:
        from experts.etl.scopus import abstracts
        logger.info('Starting abstracts...')
        abstracts.run()
        logger.info('...abstracts done.')
    if citations:
        from experts.etl.scopus import citations
        logger.info('Starting citaitons...')
        citations.run()
        logger.info('...citaitons done.')
    logger.info('...scopus done.')        
