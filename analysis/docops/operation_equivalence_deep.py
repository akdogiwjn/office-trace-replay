"""Audit residual operations against observed OPM/TLC and optional PPT cases.

Operation coverage is deliberately broader than native function identity. Every
credited family has a baseline witness; library membership alone never suffices.
Capture files and earlier accounting snapshots remain immutable.
"""
import argparse
from collections import Counter, defaultdict
import csv
import json
from pathlib import Path
import re

import operation_comparison as method
import operation_equivalence_refined as prior

ROOT = method.ROOT
INPUT = prior.INPUT
OUTPUT = 'analysis/docops/processed/operation-equivalence-deep-20261115'
POLICY = ('Observed operation families, including named Python, XML, UNO, font, '
          'pixel and shared support work; distinguish exact functions from '
          'operation coverage. Require native or frozen-workflow witnesses; retain document '
          'model paths, JPEG, blur and composition unless specifically witnessed.')


def symbol(name):
    """Normalize compiler decorations for classification, never exact identity."""
    name = name.split('@', 1)[0]
    return re.sub(r'\.(?:constprop|isra|part|lto_priv)\.\d+.*$', '', name)


def family(f):
    d, raw = f['library'], f['function']
    n = symbol(raw)
    head = n.replace('(anonymous namespace)', '{anonymous}').split('(', 1)[0]
    if head.startswith(('__aarch64_ld', '__aarch64_cas', '__aarch64_swp')):
        return '线程同步／运行时支持'
    if head.startswith(('rtl_uString', 'rtl_ustr_', 'rtl_string', 'rtl_str_')):
        return '文本比较／编码／拼接'
    if head.startswith('LanguageTag::'):
        return '语言／区域配置'
    # Ignore return types: a std::vector return value is not a container callee.
    depth = 0
    splits = []
    for i, char in enumerate(head):
        if char == '<': depth += 1
        elif char == '>': depth = max(0, depth-1)
        elif char == ' ' and depth == 0: splits.append(i)
    if splits and not head.startswith(('operator new', 'operator delete', 'non-virtual thunk')):
        head = head[splits[-1]+1:]
    # Parameter type names never establish a callee's operation.
    py = d.startswith('libpython') or re.match(r'^_?Py[A-Z_]', n)
    if py:
        if n in ('code_hash', 'code_dealloc'):
            return 'Python 对象／调用／内存管理'
        if re.match(r'^(?:_PyPegen_|_PyAST_|_PyCfg_|_PyOpcode_|compiler_|symtable_|astfold_|tok_|'
                    r'instr_sequence_to_cfg|make_cfg_traversal_stack|eliminate_empty_basic_blocks|'
                    r'translate_newlines|code_|_PyCode_)', n) or re.fullmatch(
                        r'[a-z_]+_(?:rule|raw)', n):
            return 'Python 脚本解析／编译'
        if re.match(r'^(?:_sre_|sre_|pattern_|match_|_validate_(?:inner|charset)|getstring|state_fini)', n):
            return '正则处理'
        if re.match(r'^(?:_?PyDict|_Py_dict_|dict|new_dict|new_values|free_keys_object|insertdict|'
                    r'insert_to_emptydict|resize_compact|build_indices|clone_combined_dict_keys)', n):
            return 'Python 字典／哈希管理'
        if re.match(r'^(?:_?Py(?:List|Tuple|Set|FrozenSet|Sequence|Slice|Iter)|list|tuple|set_|setiter|'
                    r'sequence_|slice|getslice|evaluate_slice_index|unpack_iterable|iter_|'
                    r'map_next|enum_|range_|deque_|newblock)', n):
            return 'Python 容器／迭代'
        if re.match(r'^(?:_?Py(?:Unicode|Bytes|ByteArray)|Py_UNICODE_|unicode|bytes_|bytearray_|'
                    r'stringlib|ucs[124]lib|charmap|do_casefold|do_upper_or_lower|lower_ucs|'
                    r'case_operation|split$|replace$|find_internal$|find_name|hashtable_unicode|'
                    r'getstring$)', n):
            return '文本比较／编码／拼接'
        if re.match(r'^(?:_?Py(?:Number|Long|Float|Bool)|long_|float_|bool_|binary_|mult(?:add)?$|'
                    r'pow5mult$|lshift$|hi0bits$|_Py_HashDouble|_Py_HashPointer|'
                    r'compute_item$|_Py_bytes_|builtin_(?:chr|ord|min|sum))', n):
            return '数值计算／转换'
        if re.match(r'^(?:_?Py(?:Err|TraceBack)|BaseException|OSError|StopIteration|tb_|'
                    r'check_except_type)', n):
            return '异常／错误处理'
        if re.match(r'^(?:_?Py(?:Object|Type|CFunction|CMethod|Function|Method|Module|Frame|Eval|Arg|'
                    r'Stack|Import|ThreadState|Thread|Leave|Enter|Mem|Callable)|'
                    r'_?Py_(?:Dealloc|XDECREF|DECREF|INCREF|RestoreSignals)|'
                    r'Py_XDECREF|Py_LeaveRecursiveCall|_Py_BaseObject|_Py_module_|'
                    r'object_|slot_|method_|cfunction_|vectorcall_|lookup_|vgetargs|va_build_value|'
                    r'subtype_|type_|func_|module_|cm_|assign_version_tag|builtin_|'
                    r'code_dealloc|data_stack|take_gil|visit_|deduce_|gc_|initialize_locals|'
                    r'check_num_args|new_values|free_keys_object)', n):
            return 'Python 对象／调用／内存管理'
    # Leaf calls imported by extension DSOs retain their actual API operation.
    if (d.startswith(('libc.so', 'libstdc++', 'libgcc')) or '@plt' in raw
            or d == '[vdso]'):
        if re.match(r'^(?:_+)?(?:memcpy|memmove|memset|malloc|calloc|realloc|free|cfree|'
                    r'_int_|operator new|operator delete)', n):
            return '内存分配／复制'
        if re.match(r'^(?:_+)?(?:str(?:cmp|ncmp|coll|cpy|ncpy|len|nlen|chr)|mem(?:cmp|chr)|'
                    r'isspace|tolower|toupper|mbrtowc)', n):
            return '文本比较／编码／拼接'
        if re.match(r'^(?:pthread_|sem_|__aarch64_|_Unwind_|__cxxabiv1::|__dynamic_cast)', n):
            return '线程同步／运行时支持'
        if re.search(r'gettime|clock|clktck', n):
            return '时钟读取'
        if re.match(r'^(?:_IO_|__GI___libc_|_?read$|_?write$|__close$|close$|'
                    r'__fseeko|lseek|open(?:64)?$|stat|fstat|access|poll|waitpid)', n):
            return '文件／进程操作'
        if n.startswith('__errno_location'):
            return '异常／错误处理'
    if d.startswith(('libgcc_s', 'libstdc++')) and re.match(
            r'^(?:uw_|get_cie_encoding|base_of_encoded_value|__cxa_)', head):
        return '线程同步／运行时支持'
    if d.startswith('libc.') and re.search(r'vfscanf|memrchr|stpcpy|_nl_|_offtime', head):
        return '文本比较／编码／拼接'
    if d.startswith('libicu') and head.startswith(('uprv_malloc', 'uprv_free')):
        return '内存分配／复制'
    if head.startswith('PORT_ZFree_Util'):
        return '内存分配／复制'
    if d.startswith('ld-linux') and n.startswith(('_dl_', 'dl_', '_start', 'do_lookup', 'check_match')):
        return '动态库装载'
    if ('std::' in head and re.search(r'std::(?:_Rb_tree|_Hashtable|vector<|deque<|'
            r'list<|map<|set<|unordered_|__detail::_(?:Map_base|Prime_rehash_policy)|pair<|_Rb_tree_)', head)):
        return 'C++ 容器／查找'
    if head.startswith(('std::__detail::__variant::', 'std::variant<', 'std::_Sp_counted_',
                        'std::_Function_handler<')):
        return 'C++ 容器／查找'
    if head.startswith('mdds::flat_segment_tree<'):
        return 'C++ 容器／查找'
    if head.startswith(('operator new', 'operator delete')):
        return '内存分配／复制'
    # Keep Word's document model separate from shared runtime callees above.
    if d in ('libswlo.so', 'libsw_writerfilterlo.so'):
        return 'Word 导入／对象布局'
    if d == 'libuno_cppu.so.3' and (head.startswith(('uno_', 'typelib_', 'cppu::'))):
        return 'UNO 数据／类型与引用管理'
    if d in ('libuno_cppuhelpergcc3.so.3', 'libcomphelper.so', 'libuno_salhelpergcc3.so.3'):
        if re.search(r'cppu::|cppuhelper::|com::sun::star::uno::|comphelper::recursivelyFindType', head):
            return 'UNO 数据／类型与引用管理'
        if re.search(r'Thread|Mutex|SolarMutex', head):
            return '线程同步／运行时支持'
    if d == 'libuno_sal.so.3':
        if head.startswith(('rtl_u', 'rtl_str', 'rtl_string', 'void rtl::str::', 'int rtl::str::',
                            'unsigned int o3tl::iterateCodePoints', 'rtl_convertUnicode', 'rtl_impl_convert')):
            return '文本比较／编码／拼接'
        if head.startswith(('rtl_math_', 'strtod_', 'jkj::', 'auto jkj::')):
            return '数值计算／转换'
        if head.startswith(('osl_', 'insertThreadId')):
            return '文件／线程平台支持'
        if head.startswith(('rtl_allocateMemory', 'rtl_freeMemory')):
            return '内存分配／复制'
    if d in ('libsvllo.so', 'libeditenglo.so') and re.search(
            r'^(?:Sfx|SvxItem|StylePool|WhichRanges|WhichRangesContainer|implCreateItemEntry|'
            r'implCleanupItemEntry|DefaultItemInstanceManager|HashedItemInstanceManager|'
            r'SvtBroadcaster|SvtListener|\{anonymous\}::(?:Sfx|Node))', head):
        return '属性／样式管理'
    if (d == 'libtllo.so' or '@plt' in raw) and re.search(r'^(?:toRational|BigInt::|Fraction::|operator==|'
            r'\{anonymous\}::checked_multiply_by)', head):
        return '数值计算／转换'
    if d == 'libm.so.6' and re.match(r'^_*(?:log|frexp|llround|round|floor|ceil|trunc|pow|sqrt)', head):
        return '数值计算／转换'
    if d in ('libsclo.so', 'libforlo.so') and head.startswith(('formula::', 'ScInterpreter::',
            'ScFormula', 'ScColumn', 'ScTable::', 'ScDocument::', 'ScToken', 'ScCell', 'ScAttr')):
        return '模型／重算'
    if d in ('libsvxcorelo.so', 'libsdlo.so') and re.search(
            r'^(?:sdr::properties::|SdrObject::GetMergedItem|SdrObject::GetViewContact|'
            r'SdrTextObj::ImpSetTextStyleSheetListeners|SdStyleSheet::GetItemSet)', head):
        return '图形对象属性管理'
    if d == 'libi18nlangtag.so' and head.startswith(('LanguageTag::', 'LanguageTagImpl::', 'MsLangId::')):
        return '语言／区域配置'
    if d in ('libi18npoollo.so',) and head.startswith(('i18npool::LocaleDataImpl::', 'NumberFormatCodeMapper::')):
        return '语言／区域配置'
    if d == 'libsvllo.so' and head.startswith('NfCurrencyEntry::'):
        return '语言／区域配置'
    if d.startswith(('libicuuc', 'libicui18n')) and re.search(r'Collat|collat', head):
        return '文本比较／编码／拼接'
    if d == 'libscfiltlo.so' and head.startswith(('XclExpFmlaCompImpl::', 'oox::xls::WorksheetGlobals::')):
        return '模型／重算'
    if head.startswith(('oox::AttributeList::', 'oox::AttributeConversion::')):
        return 'XML 解析'
    if d == 'libunoidllo.so' and head.startswith('unoidl::detail::'):
        return 'UNO 数据／类型与引用管理'
    if d == 'libconfigmgrlo.so' and head.startswith('configmgr::'):
        return '配置读取／管理'
    # XML parsing and node operations are matched across ElementTree/libxml2.
    xml = d.startswith(('etree.', '_elementpath.', '_elementtree.', 'pyexpat.', 'libxml2.'))
    if xml:
        if re.match(r'^xml(?:Str|UTF8|GetUTF8|String|Dict|Hash|Buf|EscapeText)', head):
            return 'XML 文本／名称管理'
        if re.match(r'^xml(?:XPath|XPtr|Path)', head) or re.search(r'_Element_find|element_getitem', head):
            return 'XML 节点查询／遍历'
        if re.match(r'^xml(?:New|Add|Set|Free|Unlink|Replace|Copy|Remove|Search|Get|Has|Is|Node|Doc|Ns|Reconciliate)', head) or re.search(
                r'^(?:create_new_element|element_|subelement|treebuilder_|dealloc_extra|create_extra|_elementtree_)', head):
            return 'XML 节点构建／修改'
        if re.match(r'^xml(?:SAX|Parse|Ctxt|AllocParser|InitParser|InitNode|Create|Detect|Current|Skip|Next|Char|Lookup|Push|Pop|Check|ValidateName)', head) or re.match(
                r'^(?:PyExpat_|doContent|storeAtts|normal_scan|expat_|getAttributeId|makeuniversal|checkpath)', head):
            return 'XML 解析'
        if re.match(r'^xml(?:ResetError|RaiseError)', head):
            return '异常／错误处理'
        if re.match(r'^xmlOutputBufferWrite', head):
            return '文件／进程操作'
    if d == 'libsaxlo.so' and head.startswith('sax_fastparser::'):
        return 'XML 解析'
    if d == 'libxmlreaderlo.so' and head.startswith('xmlreader::XmlReader::'):
        return 'XML 解析'
    if d == 'libooxlo.so' and head == 'oox::GetPropertyNameVector':
        return '属性／样式管理'
    if d == 'libooxlo.so' and head.startswith(('oox::Attribute', 'oox::TokenMap',
            'oox::core::ContextHandler', 'oox::core::FastParser', 'oox::core::FastTokenHandler',
            'non-virtual thunk to oox::core::FastTokenHandler')):
        return 'XML 解析'
    if d.startswith('libfreetype') and re.match(
            r'^(?:FT_|TT_|tt_|cff_|cf2_|gray_|load_truetype|ft_|sfnt_|t1_|ps_|af_|ttf_)', head):
        return '字体字形加载／栅格化'
    if (d.startswith('libfontconfig') and head.startswith('Fc')) or (d == 'libutllo.so' and re.search(
            r'FontSubstConfiguration|GetNextFontToken', head)) or (d == 'libvcllo.so' and head.startswith(
                'OutputDevice::ImplInitFontList')):
        return '字体选择／匹配'
    if d == 'libutllo.so' and re.search(r'ConfigItem|ConfigManager|SvtLinguConfig', head):
        return '配置读取／管理'
    if d == 'libutllo.so' and re.search(r'Locale|Collator|Transliteration', head):
        return '语言／区域配置'
    if d.startswith('libcairo') and re.match(r'^(?:_cairo_(?:path|clip|tor|matrix)|cairo_(?:matrix|set_line)|'
            r'curve_to|clip_and_composite|_fill_xrgb32)', head):
        return '二维路径绘制'
    if d.startswith('libpoppler') and head.startswith('Splash::drawAALine'):
        return '二维路径绘制'
    if d == 'libvcllo.so':
        if re.match(r'^vcl::(?:PDFWriterImpl|PDFExtOutDevData)::(?:emit|write|checkEmitStructure|'
                    r'initStructureElement|addInternalStructureContainer|InitStructureElement|BeginStructureElement)', head):
            return 'PDF 对象／结构写出'
        if head.startswith('vcl::PDFWriterImpl::drawLayout'):
            return '字体与文字排布'
        if head.startswith(('CairoCommon::drawPolyLine', 'OutputDevice::Push', 'OutputDevice::SetRasterOp',
                            'OutputDevice::ImplLogicToDevice', 'OutputDevice::ImplDevicePixelToLogic',
                            'ImplCalcMapResolution', 'vcl::Region::')):
            return '二维路径绘制'
        if re.search(r'(?:JPEG|jpeg_|encode_mcu_)', head):
            return 'JPEG 编解码'
        if 'stackBlur' in head:
            return '图像模糊'
        if head.startswith(('BitmapReadAccess::GetPixelFor', 'BitmapReadAccess::SetPixelFor',
                            'BitmapScoped', 'SvpSalBitmap::AcquireBuffer')) or re.search(
                                r'ImplWriteDIBBits|BitmapPalette::|^quantize$|^Bitmap::Invert', head):
            return '像素读写／格式转换'
        if re.search(r'ImplScale|ImplCalculateContributions|Lanczos\w*Kernel::|scaleUpPalette', head):
            return '图片缩放'
        if head.startswith(('vcl::Font::', 'ImplFont::', 'ImplFontCache::', 'FreetypeFontFace::',
                            'SalLayout', 'GenericSalLayout', 'hb_', '_hb_', 'vcl::font::',
                            'vcl::drawmode::GetFont', 'FreeTypeTextRenderImpl::SetFont', 'LogicalFontInstance::', 'FontAttributes::')) or re.match(r'(?:OutputDevice|VirtualDevice)::(?:'
                                r'ImplLayout|DrawText|GetText|InitFont|SetFont|ImplNewFont|SetLayoutMode|'
                                r'AttemptOLEFontScaleFix|GetFont)', head):
            return '字体与文字排布'
        if head.startswith(('SvpSalYieldMutex::', 'Application::GetSolarMutex', 'SvpSalInstance::',
                            'Application::IsQuit', 'ImplGetSVData')):
            return '线程同步／运行时支持'
    if d == 'libeditenglo.so' and head.startswith(('ImpEditEngine::', 'Outliner', 'SvxFont::')):
        return '字体与文字排布'
    if d.startswith('_imaging.'):
        if re.match(r'Imaging(?:Pack|Unpack)|get_pixel_|image_item', head):
            return '像素读写／格式转换'
        if head.startswith(('ImagingResampleHorizontal', 'ImagingResampleVertical')):
            return '图片缩放'
    if d.startswith('libMagick') and re.match(
            r'^(?:Import.*Quantum|Export.*Quantum|ExportPixelChannel|(?:Read|Write)PixelCachePixels|'
            r'Queue(?:CacheViewAuthenticPixels|AuthenticPixelCacheNexus)|'
            r'GetImagePixelCache|GetAuthenticPixels|GetVirtualPixels|GetPixelCache|SyncAuthenticPixels|'
            r'IdentifyImageGray|GetImageDepth|SetImageBackgroundColor)', head):
        return '像素读写／格式转换'
    if d.startswith('libMagick') and head.startswith(('GetImageOption', 'GetDrawInfo', 'MogrifyImageInfo')):
        return '图像参数管理'
    if d.startswith('_imaging.') and head.startswith(('image_item',)):
        return '像素读写／格式转换'
    if d.startswith('libMagick') and head.startswith('SincFast'):
        return '图片缩放'
    if d.startswith('libMagick') and head.startswith(('AcquireCriticalMemory', 'DestroySplayTree', 'Splay')):
        return '内存分配／复制' if head.startswith('Acquire') else 'C++ 容器／查找'
    if d.startswith('libgomp') and re.match(r'^(?:gomp_.*(?:wait|barrier)|omp_(?:set|unset)_lock)', head):
        return '线程同步／运行时支持'
    if d.startswith('libpixman') and head.startswith('pixman_composite_'):
        return '像素合成'
    if d.startswith('libpoppler') and head.startswith('Splash::compositeBackground'):
        return '像素合成'
    # Extra mechanisms can be witnessed by PPT candidates, never by a library name.
    if d.startswith(('libjpeg',)) or f.get('tool') == 'JPEG':
        return 'JPEG 编解码'
    if re.search(r'Composite\w*Image|AppendImages|SmushImages', head) and d.startswith('libMagick'):
        return '多图合成'
    if d == 'libooxlo.so' and head.startswith('oox::drawingml::table::'):
        return '幻灯片表格样式'
    return prior.family(f)


def witnesses(cases):
    out = defaultdict(list)
    for p, c in cases.items():
        for f in c['functions']:
            g = family(f)
            if g:
                out[g].append(dict(reference=p, **f))
    # Prefer descriptive witnesses in the human-readable audit, retaining all.
    preferred = {
        'Python 对象／调用／内存管理': 'PyObject_Vectorcall',
        'Python 字典／哈希管理': '_Py_dict_lookup',
        'Python 容器／迭代': 'list_iter',
        '数值计算／转换': '_PyLong_Subtract',
        'XML 节点构建／修改': 'create_new_element',
        '字体与文字排布': 'ImpEditEngine::CreateLines',
    }
    for g, rows in out.items():
        rows.sort(key=lambda f: (not f['function'].startswith(preferred.get(g, '\0')),
                                 f['reference'], -f['period']))
    return dict(out)


def refine(c, proof):
    """Only move residual known functions, preserving exact and unknown periods."""
    out = dict(c)
    counts, ops, sep, tools, added = (Counter() for _ in range(5))
    fs = []
    for saved in c['functions']:
        f = dict(saved, previous_bucket=saved['bucket'])
        g = family(f)
        if f['bucket'] in ('separate_operation', 'other_resolved') and proof.get(g):
            f.update(bucket='same_operation', operation=g, evidence_family=g,
                     evidence_reference=proof[g][0]['reference'],
                     evidence_library=proof[g][0]['library'],
                     evidence_function=proof[g][0]['function'],
                     evidence_kind=proof[g][0].get('evidence_kind','native_function'),
                     evidence_source=proof[g][0].get('source_path'))
            added[g] += f['period']
        elif f['bucket'] in ('separate_operation', 'other_resolved') and g in (
                'Word 导入／对象布局', 'JPEG 编解码', '图像模糊', '多图合成', '幻灯片表格样式'):
            f.update(bucket='separate_operation', operation=g)
        counts[f['bucket']] += f['period']
        if f['bucket'] == 'same_operation': ops[f['operation']] += f['period']
        if f['bucket'] == 'separate_operation': sep[f['operation']] += f['period']
        if f['bucket'] == 'other_resolved': tools[f['tool']] += f['period']
        fs.append(f)
    counts['unresolved'] = c['periods']['unresolved']
    for k in ('exact', 'same_operation', 'separate_operation', 'other_resolved'):
        counts.setdefault(k, 0)
    assert sum(counts.values()) == c['roi_period']
    assert counts['exact'] == c['periods']['exact']
    assert counts['same_operation'] == c['periods']['same_operation'] + sum(added.values())
    grouped = lambda vals, label: [dict(**{label: k}, period=v,
                                      share_pct=100*v/c['roi_period']) for k, v in vals.most_common()]
    out.update(functions=fs, periods=dict(counts),
               shares_pct={k: 100*v/c['roi_period'] for k, v in counts.items()},
               supported_share_pct=100*(counts['exact']+counts['same_operation'])/c['roi_period'],
               previous_supported_share_pct=c['supported_share_pct'],
               additional_share_pct=100*sum(added.values())/c['roi_period'],
               same_operations=grouped(ops, 'operation'),
               additional_operations=grouped(added, 'operation'),
               separate_operations=grouped(sep, 'operation'), other_tools=grouped(tools, 'tool'))
    return out


def supplement(c, raw, selected):
    """Marginal gain of original candidates on top of old-operation coverage."""
    proof = witnesses({p: raw['cases'][p] for p in selected})
    exact = {method.key(f): p for p in selected for f in raw['cases'][p]['functions']}
    gains = Counter()
    rows = []
    for f in c['functions']:
        if f['bucket'] not in ('separate_operation', 'other_resolved'):
            continue
        g = family(f)
        mode = 'function' if method.key(f) in exact else 'operation' if proof.get(g) else None
        if mode:
            gains[mode] += f['period']
            rows.append(dict(f, gain_mode=mode,
                             candidate=exact[method.key(f)] if mode == 'function' else proof[g][0]['reference'],
                             candidate_family=g,
                             candidate_witness=None if mode == 'function' else proof[g][0]))
    gain = sum(gains.values())
    return dict(candidates=selected, added_period=gain,
                added_share_pct=100*gain/c['roi_period'],
                supported_share_pct=c['supported_share_pct']+100*gain/c['roi_period'],
                gain_periods=dict(gains), functions=rows)


def gather():
    old = prior.load()
    raw = json.loads((ROOT/INPUT/'comparison.json').read_text())
    for p, h in raw['input_sha256'].items():
        assert method.sha(ROOT/p) == h, p
    proof = witnesses(raw['references'])
    # OPM's Python-level PDF writer has no distinct native leaf name. Bind its
    # executed script to the frozen workload lock instead of inventing a symbol.
    script = 'document-oe/assets/skills/pdf/scripts/fill_fillable_fields.py'
    lock_path = 'document-oe/lock.json'
    lock = json.loads((ROOT/lock_path).read_text())
    assert method.sha(ROOT/script) == lock['workload_files']['skills/pdf/scripts/fill_fillable_fields.py']['sha256']
    assert any(p['script']=='fill_fillable_fields.py' for p in raw['references']['OPM']['processes'])
    source = (ROOT/script).read_text()
    assert 'writer = PdfWriter(clone_from=reader)' in source and 'writer.write(f)' in source
    proof['PDF 对象／结构写出'] = [dict(reference='OPM', library='pypdf (frozen workflow)',
        function='fill_pdf_fields: PdfWriter.write(f)', evidence_kind='workflow_source',
        source_path=script, source_sha256=method.sha(ROOT/script), lock_path=lock_path)]
    cases = {p: refine(c, proof) for p, c in old['cases'].items()}
    supplements = {p: {','.join(ids): supplement(c, raw, ids) for ids in
                      (['021'], ['026'], ['029'], ['021', '026', '029'])}
                   for p, c in cases.items()}
    ppt = cases['021']
    remaining = [f for f in ppt['functions'] if f['bucket'] in ('separate_operation', 'other_resolved')]
    return dict(schema='deep-operation-review-v1', policy=POLICY, cases=cases,
                reference_witnesses=proof, supplements=supplements,
                ppt021=dict(top_function=max(remaining, key=lambda f:f['period']),
                            document_operation_pct=ppt['shares_pct']['separate_operation'],
                            operation_groups=ppt['separate_operations']),
                inputs={prior.OUTPUT+'/comparison.json': method.sha(ROOT/prior.OUTPUT/'comparison.json'),
                        prior.OUTPUT+'/analysis-build.json': method.sha(ROOT/prior.OUTPUT/'analysis-build.json'),
                        INPUT+'/comparison.json': method.sha(ROOT/INPUT/'comparison.json'),
                        script: method.sha(ROOT/script), lock_path: method.sha(ROOT/lock_path)},
                verification=dict(status='passed', input_hashes_checked=len(raw['input_sha256']),
                                  full_periods_conserved=True, exact_periods_unchanged=True,
                                  unknown_periods_unchanged=True),
                workload_or_collector_run=False, html_modified=False)


def load():
    folder = ROOT/OUTPUT
    b = json.loads((folder/'analysis-build.json').read_text())
    for p, h in b['source_sha256'].items(): assert method.sha(ROOT/p) == h, p
    for p, h in b['inputs'].items(): assert method.sha(ROOT/p) == h, p
    for p, h in b['outputs'].items(): assert method.sha(folder/p) == h, p
    return json.loads((folder/'comparison.json').read_text())


def save(data):
    folder = ROOT/OUTPUT
    folder.mkdir(parents=True, exist_ok=False)
    method.write(folder/'comparison.json', data)
    with (folder/'functions.csv').open('w', newline='') as stream:
        fields = ['task', 'library', 'function', 'period', 'bucket', 'operation',
                  'previous_bucket', 'evidence_reference', 'evidence_library', 'evidence_function',
                  'evidence_kind', 'evidence_source']
        w = csv.DictWriter(stream, fields, extrasaction='ignore'); w.writeheader()
        for c in data['cases'].values():
            for f in c['functions']: w.writerow(dict(task=c['task'], **f))
    rows = [[c['task'], *[f'{v:.2f}%' for v in (
        c['shares_pct']['exact'], c['previous_supported_share_pct'], c['additional_share_pct'],
        c['supported_share_pct'], c['shares_pct']['separate_operation'],
        c['shares_pct']['other_resolved'], c['shares_pct']['unresolved'])]] for c in data['cases'].values()]
    lines = ['# 公共操作深度核对', '',
             '按具体函数用途归并，每类均保留旧 OPM／TLC 的实际函数或冻结执行脚本依据。精确函数匹配不变；操作覆盖描述工作类型，不代表算法或 CPU 压力相同。', '',
             '归并粒度：Python 容器／调用／编译、XML 节点／文本处理、UNO 数据／类型管理等为公共操作族。'
             '例如 ElementTree find 与 XPath 查询都归入节点查询，Pillow RGB 打包与位图写入都归入像素格式处理；'
             '同类不要求算法、编码格式或内部执行路径相同。JPEG、图像模糊、多页拼图与专用文档模型单独核验。', '',
             method.table(['大档', '函数匹配', '上版操作覆盖', '本次补充', '操作覆盖', '文档路径剩余', '其余已解析', '未解析'], rows), '',
             'PDF 对象写出另用 OPM 实际执行的 fill_fillable_fields.py 为证据：PdfWriter.write(f)；文件 SHA256 与 document-oe/lock.json 相符，且旧采样记录包含该脚本。此项是工作流证据，不虚构原生函数匹配。', '',
             '## Word 009 与原始 PPT 的交叉覆盖', '',
             method.table(['追加原始任务', '新增覆盖', '合计覆盖'],
                [[k, f"{v['added_share_pct']:.2f}%", f"{v['supported_share_pct']:.2f}%"]
                 for k,v in data['supplements']['009'].items()]), '',
             '## 追加 PPT 021 后的逐例覆盖', '',
             method.table(['大档任务', '旧两例操作覆盖', '追加原始 021', '增益'],
                [[p, f"{c['supported_share_pct']:.2f}%",
                  f"{data['supplements'][p]['021']['supported_share_pct']:.2f}%",
                  f"{data['supplements'][p]['021']['added_share_pct']:.2f}%"]
                 for p,c in data['cases'].items()]), '',
             '## 本次新增归并与旧例依据', '']
    added = {g['operation'] for c in data['cases'].values() for g in c['additional_operations']}
    for g in sorted(added):
        example = data['reference_witnesses'][g][0]
        lines += ['- '+g+'：'+example['reference']+'／`'+example['library']+'`／`'+example['function']+'`。']
    lines += ['', '## 剩余函数审阅', '',
              '下面展示各例尚未归并的主要函数，不把这些全部称为新操作；functions.csv 保留全量账本。', '']
    for p,c in data['cases'].items():
        fs = sorted((f for f in c['functions'] if f['bucket'] == 'other_resolved'), key=lambda f:-f['period'])
        lines += ['### '+p, '', method.table(['库', '函数', '整轮权重'],
            [[f['library'], '`'+f['function'].replace('|', '\\|')+'`', f"{100*f['period']/c['roi_period']:.3f}%"] for f in fs[:12]]), '']
    (folder/'analysis.md').write_text('\n'.join(lines))
    method.write(folder/'analysis-build.json', dict(
        source_sha256={str(Path(__file__).relative_to(ROOT)): method.sha(__file__),
                       'analysis/docops/operation_equivalence_refined.py': method.sha(ROOT/'analysis/docops/operation_equivalence_refined.py')},
        inputs=data['inputs'], outputs={p.name: method.sha(p) for p in folder.iterdir() if p.is_file()},
        workload_or_collector_run=False, html_modified=False))
    print(folder)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--build', required=True, action='store_true')
    parser.parse_args()
    save(gather())
