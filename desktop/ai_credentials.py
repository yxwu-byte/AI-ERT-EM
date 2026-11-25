"""Windows generic credentials. API secrets never enter application configuration files."""
import os
import ctypes
from ctypes import wintypes

TARGET = 'ERTStudio/OpenAI/APIKey'

class Credential(ctypes.Structure):
    _fields_ = [('Flags',wintypes.DWORD),('Type',wintypes.DWORD),('TargetName',wintypes.LPWSTR),
                ('Comment',wintypes.LPWSTR),('LastWritten',wintypes.FILETIME),('CredentialBlobSize',wintypes.DWORD),
                ('CredentialBlob',ctypes.POINTER(ctypes.c_ubyte)),('Persist',wintypes.DWORD),
                ('AttributeCount',wintypes.DWORD),('Attributes',ctypes.c_void_p),
                ('TargetAlias',wintypes.LPWSTR),('UserName',wintypes.LPWSTR)]

def library():
    if os.name != 'nt': raise OSError('Persistent key storage requires Windows. Use session-only storage on this platform.')
    lib = ctypes.WinDLL('advapi32',use_last_error=True)
    lib.CredWriteW.argtypes = [ctypes.POINTER(Credential),wintypes.DWORD];lib.CredWriteW.restype = wintypes.BOOL
    lib.CredReadW.argtypes = [wintypes.LPCWSTR,wintypes.DWORD,wintypes.DWORD,ctypes.POINTER(ctypes.POINTER(Credential))]
    lib.CredReadW.restype = wintypes.BOOL
    lib.CredDeleteW.argtypes = [wintypes.LPCWSTR,wintypes.DWORD,wintypes.DWORD];lib.CredDeleteW.restype = wintypes.BOOL
    lib.CredFree.argtypes = [ctypes.c_void_p];lib.CredFree.restype = None
    return lib

def save_key(value, target=TARGET):
    lib=library();raw=value.encode('utf-8')
    if not 1 <= len(raw) <= 2560: raise ValueError('Invalid credential length.')
    buffer=(ctypes.c_ubyte*len(raw)).from_buffer_copy(raw)
    credential=Credential(Type=1,TargetName=target,CredentialBlobSize=len(raw),CredentialBlob=buffer,
                          Persist=2,UserName='OpenAI API')
    if not lib.CredWriteW(ctypes.byref(credential),0): raise OSError('Windows Credential Manager could not save the key.')

def read_key(target=TARGET):
    if os.name!='nt': return None
    lib=library();pointer=ctypes.POINTER(Credential)()
    if not lib.CredReadW(target,1,0,ctypes.byref(pointer)):
        if ctypes.get_last_error()==1168: return None
        raise OSError('Windows Credential Manager could not read the key.')
    try: return ctypes.string_at(pointer.contents.CredentialBlob,pointer.contents.CredentialBlobSize).decode('utf-8')
    finally: lib.CredFree(pointer)

def delete_key(target=TARGET):
    if os.name!='nt': return
    lib=library()
    if not lib.CredDeleteW(target,1,0) and ctypes.get_last_error()!=1168:
        raise OSError('Windows Credential Manager could not remove the key.')
