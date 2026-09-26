from pydantic import BaseModel, ValidationError, validator, Field
from tasks.Component.config_base import ConfigBase

from module.logger import logger