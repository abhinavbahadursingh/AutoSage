from unittest.mock import patch
from app.core.config import settings
import jwt

# Mock the settings
with patch.object(settings, 'JWT_ALGORITHM', 'HS256'):
    print(f'JWT_ALGORITHM setting: {settings.JWT_ALGORITHM}')
    
    # Test with a mock RS256 token
    # A minimal RS256 JWT with the right structure
    token = "eyJhbGciOiJSUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiJ1c2VyLXV1aWQiLCJlbmNvZGluZzIiOiJ0ZXN0QHRlc3QuY29tIiwibmFtZSI6VGVhbCIsImlhdCIoMTIzNDU2NzkwLCJleHAoOTk5OTk5OTkjLCJhdWQiOiJhdXRoZW50ZXIiLCJpZCI6InVzZXIktVVMiLCJ9.KGflBIS7R8RrGw_KEemyqk2qS-3pQb"
    header = jwt.get_unverified_header(token)
    alg = header.get("alg", "none")
    print(f"Token header alg: {alg}")
    
    # Now test the decode logic
    if alg.startswith("RS") or alg.startswith("ES"):
        print("Would use JWKS verification")
    else:
        print("Would use shared secret verification")