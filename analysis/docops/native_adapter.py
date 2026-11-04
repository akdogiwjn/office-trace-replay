"""DocOps parser compatibility: C++ anonymous namespaces are part of the symbol."""
import re
import native_profile

# The last parenthesized path is the DSO. Earlier " (anonymous namespace)"
# segments belong to the C++ symbol, not the library name. Original seven-case
# code and archived exports remain unchanged.
native_profile.FRAME=re.compile(r'^\s+([a-fA-F0-9]+)\s+(.+)\s+\((/.*|\[.*\]|inlined)\)\s*$')

parse=native_profile.parse
attribute=native_profile.attribute
crosscheck=native_profile.crosscheck
loss_diagnostics=native_profile.loss_diagnostics
profile=native_profile.profile


def leaf_records(path):
    """Streaming original leaf records; avoids holding a second full call stack."""
    current=None
    with open(path)as stream:
        for line in stream:
            if line.startswith('\t')and current is not None and current.get('leaf')is not None:
                continue
            header=native_profile.HEADER.match(line)
            if header:
                if current is not None:yield current
                pid,tid,stamp,period,event=native_profile.key(header)
                current={'key':(pid,tid,stamp,period,event),'leaf':None}
            elif current is not None and current['leaf']is None:
                frame=native_profile.FRAME.match(line)
                if frame:
                    address,_,dso=frame.groups();current['leaf']=(address,dso)
                elif line.strip()and re.match(r'^\s+[0-9a-fA-F]+\s+',line):
                    raise ValueError('unrecognized original physical leaf')
    if current is not None:yield current
