# -*- coding: utf-8 -*-
import os
import zipfile
import tarfile
from typing import Generator, BinaryIO, Optional
from io import BytesIO


CHUNK_SIZE = 64 * 1024


def stream_file(filepath: str, chunk_size: int = CHUNK_SIZE) -> Generator[bytes, None, None]:
    with open(filepath, 'rb') as f:
        while True:
            chunk = f.read(chunk_size)
            if not chunk:
                break
            yield chunk


def stream_zip_directory(folder_path: str, chunk_size: int = CHUNK_SIZE) -> Generator[bytes, None, None]:
    class ChunkedZipWriter:
        def __init__(self, chunk_size: int):
            self._buffer = BytesIO()
            self._chunk_size = chunk_size
            self._zip = zipfile.ZipFile(self._buffer, 'w', zipfile.ZIP_DEFLATED)
        
        def write_file(self, filepath: str, arcname: str):
            self._zip.write(filepath, arcname)
            if self._buffer.tell() >= self._chunk_size:
                self._buffer.seek(0)
                while True:
                    chunk = self._buffer.read(self._chunk_size)
                    if not chunk:
                        break
                    yield chunk
                self._buffer = BytesIO()
                self._zip = zipfile.ZipFile(self._buffer, 'w', zipfile.ZIP_DEFLATED, append=True)
        
        def close(self):
            self._zip.close()
            self._buffer.seek(0)
            while True:
                chunk = self._buffer.read(self._chunk_size)
                if not chunk:
                    break
                yield chunk
    
    writer = ChunkedZipWriter(chunk_size)
    for root, dirs, files in os.walk(folder_path):
        for file in files:
            file_path = os.path.join(root, file)
            arcname = os.path.relpath(file_path, folder_path)
            yield from writer.write_file(file_path, arcname)
    yield from writer.close()


def stream_tar_directory(folder_path: str, chunk_size: int = CHUNK_SIZE) -> Generator[bytes, None, None]:
    buffer = BytesIO()
    
    with tarfile.open(fileobj=buffer, mode='w') as tar:
        for root, dirs, files in os.walk(folder_path):
            for file in files:
                file_path = os.path.join(root, file)
                arcname = os.path.relpath(file_path, folder_path)
                tar.add(file_path, arcname)
                
                if buffer.tell() >= chunk_size * 10:
                    buffer.seek(0)
                    while buffer.tell() < buffer.getbuffer().nbytes:
                        chunk = buffer.read(chunk_size)
                        if chunk:
                            yield chunk
                    buffer = BytesIO()
    
    buffer.seek(0)
    while True:
        chunk = buffer.read(chunk_size)
        if not chunk:
            break
        yield chunk


class StreamingZipFile:
    def __init__(self):
        self._buffer = BytesIO()
        self._zip = zipfile.ZipFile(self._buffer, 'w', zipfile.ZIP_DEFLATED)
        self._closed = False
    
    def add_file(self, filepath: str, arcname: str):
        self._zip.write(filepath, arcname)
    
    def add_file_from_stream(self, file_obj: BinaryIO, arcname: str, file_size: int):
        self._zip.writestr(arcname, file_obj.read())
    
    def close(self):
        self._zip.close()
        self._closed = True
        self._buffer.seek(0)
    
    def read_chunk(self, chunk_size: int = CHUNK_SIZE) -> Optional[bytes]:
        if not self._closed:
            raise RuntimeError("ZipFile must be closed before reading")
        return self._buffer.read(chunk_size)
    
    def stream(self, chunk_size: int = CHUNK_SIZE) -> Generator[bytes, None, None]:
        self.close()
        while True:
            chunk = self.read_chunk(chunk_size)
            if not chunk:
                break
            yield chunk


def true_streaming_zip(folder_path: str, chunk_size: int = CHUNK_SIZE) -> Generator[bytes, None, None]:
    import struct
    import zlib
    
    CRC_UNKNOWN = 0
    local_file_header_sig = b'PK\x03\x04'
    central_dir_header_sig = b'PK\x01\x02'
    end_central_dir_sig = b'PK\x05\x06'
    
    central_dir_entries = []
    central_dir_size = 0
    central_dir_offset = 0
    offset = 0
    
    def write_chunk(data: bytes):
        nonlocal offset
        offset += len(data)
        return data
    
    for root, dirs, files in os.walk(folder_path):
        for filename in files:
            filepath = os.path.join(root, filename)
            arcname = os.path.relpath(filepath, folder_path).replace('\\', '/')
            
            file_stat = os.stat(filepath)
            file_size = file_stat.st_size
            mod_time = int(file_stat.st_mtime)
            
            dos_time = ((mod_time & 0x1F) << 11) | (((mod_time >> 5) & 0x3F) << 5) | ((mod_time >> 11) & 0x1F)
            dos_date = (((mod_time >> 16) & 0x1F) << 9) | (((mod_time >> 21) & 0xF) << 5) | ((mod_time >> 25) & 0x7F)
            
            crc = 0
            with open(filepath, 'rb') as f:
                crc = zlib.crc32(f.read()) & 0xFFFFFFFF
            
            local_header = local_file_header_sig
            local_header += struct.pack('<HHHHHIIIHH', 20, 0, 0, 0, dos_time, dos_date, crc, file_size, file_size, len(arcname), 0)
            local_header += arcname.encode('utf-8')
            
            yield write_chunk(local_header)
            
            with open(filepath, 'rb') as f:
                while True:
                    chunk = f.read(chunk_size)
                    if not chunk:
                        break
                    yield write_chunk(chunk)
            
            central_dir_entries.append({
                'arcname': arcname,
                'crc': crc,
                'compressed_size': file_size,
                'uncompressed_size': file_size,
                'dos_time': dos_time,
                'dos_date': dos_date,
                'local_offset': offset - file_size - len(local_header)
            })
    
    central_dir_offset = offset
    
    for entry in central_dir_entries:
        central_header = central_dir_header_sig
        central_header += struct.pack('<HHHHHHIIIHHHHHII',
            20, 20, 0, 0, 0,
            entry['dos_time'], entry['dos_date'],
            entry['crc'],
            entry['compressed_size'],
            entry['uncompressed_size'],
            len(entry['arcname']), 0, 0, 0, 0,
            entry['local_offset']
        )
        central_header += entry['arcname'].encode('utf-8')
        central_dir_size += len(central_header)
        yield write_chunk(central_header)
    
    end_record = end_central_dir_sig
    end_record += struct.pack('<HHHHIIH',
        0, 0,
        len(central_dir_entries),
        len(central_dir_entries),
        central_dir_size,
        central_dir_offset,
        0
    )
    yield write_chunk(end_record)
