import inspect
from agno.models.openai import OpenAIResponses

print('OpenAIResponses signature:', inspect.signature(OpenAIResponses))
public = [m for m in dir(OpenAIResponses) if not m.startswith('_')]
print('OpenAIResponses public methods:', public)

# Try to find an abstract/base Responses class
import pkgutil, agno.models
for _, modname, _ in pkgutil.iter_modules(agno.models.__path__):
    if modname != 'openai':
        print('found model module:', modname)

# Attempt to inspect a known base type if available
try:
    from agno.models import base as base_mod
    print('Found agno.models.base:', [m for m in dir(base_mod) if not m.startswith('_')])
except Exception as e:
    print('agno.models.base not available:', e)
