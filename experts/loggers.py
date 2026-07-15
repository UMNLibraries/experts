"""Structured logging utilities for Experts ETL and API record pipelines."""

from datetime import datetime
import json
import logging
from logging.handlers import TimedRotatingFileHandler
import os
import shutil
import gzip
import traceback

from pythonjsonlogger import jsonlogger

# defaults

dirname = os.path.dirname(os.path.realpath(__file__ + '/..'))
if 'EXPERTS_ETL_LOG_DIR' in os.environ:
  dirname = os.environ['EXPERTS_ETL_LOG_DIR']

# formatters

class PureApiRecordFormatter(logging.Formatter):
  """Formatter that normalizes API record messages to one-line JSON."""

  def format(self, record):
    """Formats a log record message as compact JSON.

    Args:
      record: Logging record to format.

    Returns:
      JSON string for string/dict messages.
    """
    if isinstance(record.msg, str):
      # Ensure we get a single-line record by loading and then dumping:
      return json.dumps(json.loads(record.msg))
    elif isinstance(record.msg, dict):
      return json.dumps(record.msg)

class ExpertsEtlFormatter(jsonlogger.JsonFormatter):
  """JSON formatter that ensures ETL records include a UTC timestamp."""

  def add_fields(self, log_record, record, message_dict):
    """Adds standard fields and a fallback timestamp to ETL log records.

    Args:
      log_record: Mutable output mapping for serialized log fields.
      record: Source logging record.
      message_dict: Structured message payload from the logger call.
    """
    super(ExpertsEtlFormatter, self).add_fields(log_record, record, message_dict)
    if not log_record.get('timestamp'):
      # This doesn't use record.created, so it will be slightly off.
      log_record['timestamp'] = datetime.utcnow().strftime('%Y-%m-%dT%H:%M:%S.%fZ')

def namer(name):
  """Appends a gzip extension to rotated log file names.

  Args:
    name: Rotated log file path.

  Returns:
    File path with .gz suffix.
  """
  return name + '.gz'

def rotator(source, dest):
  """Compresses a rotated log file and removes the uncompressed source.

  Args:
    source: Source path of the rotated file.
    dest: Destination path for the compressed file.
  """
  with open(source, 'rb') as sf:
    with gzip.open(dest, 'wb') as df:
      shutil.copyfileobj(sf, df)
  os.remove(source)

def pure_api_record_logger(name='pure_api_record', dirname=dirname, type='pure-api-record-type'):
  """Creates a timed rotating logger for API record payload logs.

  Args:
    name: Logger name suffix under experts_etl namespace.
    dirname: Directory where log files are written.
    type: Filename stem for the log file.

  Returns:
    Configured logger instance.
  """
  path = dirname + '/' + type + '.log'
  logger = logging.getLogger('experts_etl.' + name)
  logger.setLevel(logging.INFO)

  handler = TimedRotatingFileHandler(
    path,
    when='S',
    interval=86400, # seconds/day
    backupCount=365
  )
  handler.setFormatter(PureApiRecordFormatter())
  handler.rotator = rotator
  handler.namer = namer
  logger.addHandler(handler)

  return logger

def experts_etl_logger(name='experts_etl', dirname=dirname):
  """Creates a timed rotating logger for general ETL operational logs.

  Args:
    name: Logger name suffix under experts_etl namespace.
    dirname: Directory where log files are written.

  Returns:
    Configured logger instance.
  """
  path = dirname + '/' + name + '.log'
  logger = logging.getLogger('experts_etl.' + name)
  logger.setLevel(logging.INFO)

  handler = TimedRotatingFileHandler(
    path,
    when='S',
    interval=86400, # seconds/day
    backupCount=365
  )
  handler.setFormatter(ExpertsEtlFormatter(
    '%(timestamp)s %(levelname)s %(name)s %(message)s %(pathname)s %(funcName)s %(lineno)i'
  ))
  handler.rotator = rotator
  handler.namer = namer

  logger.addHandler(handler)

  return logger

def rollover(logger):
  """Forces immediate rollover on the first timed rotating file handler.

  Args:
    logger: Logger whose handlers are scanned for rollover support.
  """
  for handler in logger.handlers:
    if isinstance(handler, TimedRotatingFileHandler):
      handler.doRollover()
      break

def format_exception(e):
    """Formats an exception and traceback into a single string.

    Args:
        e: Exception to format.

    Returns:
        Formatted traceback string.
    """
    # Inspired by: https://realpython.com/the-most-diabolical-python-antipattern/
    tb_lines = traceback.format_exception(e.__class__, e, e.__traceback__)
    return ''.join(tb_lines)
