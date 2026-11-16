# 公共操作深度核对

按具体函数用途归并，每类均保留旧 OPM／TLC 的实际函数或冻结执行脚本依据。精确函数匹配不变；操作覆盖描述工作类型，不代表算法或 CPU 压力相同。

归并粒度：Python 容器／调用／编译、XML 节点／文本处理、UNO 数据／类型管理等为公共操作族。例如 ElementTree find 与 XPath 查询都归入节点查询，Pillow RGB 打包与位图写入都归入像素格式处理；同类不要求算法、编码格式或内部执行路径相同。JPEG、图像模糊、多页拼图与专用文档模型单独核验。

| 大档 | 函数匹配 | 上版操作覆盖 | 本次补充 | 操作覆盖 | 文档路径剩余 | 其余已解析 | 未解析 |
|---|---|---|---|---|---|---|---|
| 001-u500 | 75.56% | 90.19% | 3.63% | 93.82% | 2.51% | 0.27% | 3.40% |
| 003-u500 | 71.58% | 96.60% | 0.91% | 97.51% | 0.87% | 0.14% | 1.48% |
| 009-u500 | 71.59% | 80.58% | 6.69% | 87.27% | 8.26% | 1.02% | 3.46% |
| 013-v1000 | 93.25% | 95.79% | 4.00% | 99.79% | 0.16% | 0.04% | 0.02% |
| 014-n10000 | 91.82% | 96.68% | 1.78% | 98.46% | 0.01% | 0.47% | 1.05% |
| 016-u500 | 80.03% | 87.79% | 10.31% | 98.10% | 0.28% | 1.07% | 0.55% |
| 021-g10 | 50.44% | 75.76% | 8.56% | 84.32% | 12.50% | 1.07% | 2.11% |
| 026-u10 | 63.00% | 77.20% | 9.12% | 86.32% | 11.20% | 0.60% | 1.87% |
| 029-u10 | 46.29% | 56.15% | 24.51% | 80.66% | 8.56% | 3.93% | 6.84% |
| 031-u20 | 86.49% | 97.79% | 2.21% | 100.00% | 0.00% | 0.00% | 0.00% |
| 037-u20 | 86.72% | 98.55% | 1.45% | 100.00% | 0.00% | 0.00% | 0.00% |
| pdfwf005-u20 | 48.94% | 94.07% | 3.96% | 98.03% | 1.17% | 0.38% | 0.43% |

PDF 对象写出另用 OPM 实际执行的 fill_fillable_fields.py 为证据：PdfWriter.write(f)；文件 SHA256 与 document-oe/lock.json 相符，且旧采样记录包含该脚本。此项是工作流证据，不虚构原生函数匹配。

## Word 009 与原始 PPT 的交叉覆盖

| 追加原始任务 | 新增覆盖 | 合计覆盖 |
|---|---|---|
| 021 | 0.28% | 87.54% |
| 026 | 0.08% | 87.34% |
| 029 | 0.20% | 87.47% |
| 021,026,029 | 0.38% | 87.65% |

## 追加 PPT 021 后的逐例覆盖

| 大档任务 | 旧两例操作覆盖 | 追加原始 021 | 增益 |
|---|---|---|---|
| 001 | 93.82% | 94.02% | 0.20% |
| 003 | 97.51% | 97.55% | 0.05% |
| 009 | 87.27% | 87.54% | 0.28% |
| 013 | 99.79% | 99.94% | 0.15% |
| 014 | 98.46% | 98.52% | 0.06% |
| 016 | 98.10% | 98.36% | 0.26% |
| 021 | 84.32% | 95.12% | 10.80% |
| 026 | 86.32% | 95.62% | 9.29% |
| 029 | 80.66% | 86.29% | 5.62% |
| 031 | 100.00% | 100.00% | 0.00% |
| 037 | 100.00% | 100.00% | 0.00% |
| pdfwf005 | 98.03% | 99.19% | 1.17% |

## 本次新增归并与旧例依据

- C++ 容器／查找：OPM／`libpoppler.so.133.0.0`／`std::_Hashtable<std::__cxx11::basic_string<char, std::char_traits<char>, std::allocator<char> >, std::pair<std::__cxx11::basic_string<char, std::char_traits<char>, std::allocator<char> > const, int>, std::allocator<std::pair<std::__cxx11::basic_string<char, std::char_traits<char>, std::allocator<char> > const, int> >, std::__detail::_Select1st, std::equal_to<std::__cxx11::basic_string<char, std::char_traits<char>, std::allocator<char> > >, std::hash<std::__cxx11::basic_string<char, std::char_traits<char>, std::allocator<char> > >, std::__detail::_Mod_range_hashing, std::__detail::_Default_ranged_hash, std::__detail::_Prime_rehash_policy, std::__detail::_Hashtable_traits<true, false, true> >::_M_insert_unique_node(unsigned long, unsigned long, std::__detail::_Hash_node<std::pair<std::__cxx11::basic_string<char, std::char_traits<char>, std::allocator<char> > const, int>, true>*, unsigned long)`。
- PDF 对象／结构写出：OPM／`pypdf (frozen workflow)`／`fill_pdf_fields: PdfWriter.write(f)`。
- Python 字典／哈希管理：OPM／`libpython3.12.so.1.0`／`_Py_dict_lookup`。
- Python 容器／迭代：TLC／`libpython3.12.so.1.0`／`list_iter`。
- Python 对象／调用／内存管理：TLC／`libpython3.12.so.1.0`／`PyObject_Vectorcall`。
- Python 脚本解析／编译：OPM／`libpython3.12.so.1.0`／`_PyCfg_OptimizeCodeUnit.isra.0`。
- UNO 数据／类型与引用管理：TLC／`libuno_cppuhelpergcc3.so.3`／`cppu::OWeakObject::acquire()`。
- XML 文本／名称管理：TLC／`libxml2.so.16`／`xmlDictFindEntry`。
- XML 节点构建／修改：TLC／`_elementtree.cpython-312-aarch64-linux-gnu.so`／`create_new_element.isra.0`。
- XML 节点查询／遍历：TLC／`_elementtree.cpython-312-aarch64-linux-gnu.so`／`_elementtree_Element_findtext`。
- XML 解析：TLC／`pyexpat.cpython-312-aarch64-linux-gnu.so`／`storeAtts`。
- 二维路径绘制：OPM／`libpoppler.so.133.0.0`／`Splash::drawAALine(SplashPipe*, int, int, int, bool, unsigned char)`。
- 像素合成：OPM／`libpoppler.so.133.0.0`／`Splash::compositeBackground(unsigned char const*)`。
- 像素读写／格式转换：OPM／`_imaging.cpython-312-aarch64-linux-gnu.so`／`ImagingUnpackRGB`。
- 内存分配／复制：OPM／`libc.so.6`／`__memcpy_generic`。
- 动态库装载：OPM／`ld-linux-aarch64.so.1`／`_dl_tlsdesc_return`。
- 图形对象属性管理：TLC／`libsvxcorelo.so`／`SdrObject::GetViewContact() const`。
- 图片缩放：OPM／`_imaging.cpython-312-aarch64-linux-gnu.so`／`ImagingResampleHorizontal_8bpc`。
- 字体与文字排布：TLC／`libeditenglo.so`／`ImpEditEngine::CreateLines(int, unsigned int)`。
- 字体字形加载／栅格化：OPM／`libfreetype.so.6.20.1`／`gray_convert_glyph`。
- 字体选择／匹配：TLC／`libutllo.so`／`utl::FontSubstConfiguration::getSubstInfo(rtl::OUString const&) const`。
- 属性／样式管理：TLC／`libsvllo.so`／`SfxItemPool::GetUserOrPoolDefaultItem(unsigned short) const`。
- 异常／错误处理：OPM／`libpython3.12.so.1.0`／`PyErr_GivenExceptionMatches`。
- 数值计算／转换：TLC／`libpython3.12.so.1.0`／`_PyLong_Subtract`。
- 文件／线程平台支持：TLC／`libuno_sal.so.3`／`osl_acquireMutex`。
- 文件／进程操作：OPM／`libc.so.6`／`__fseeko64`。
- 文本比较／编码／拼接：OPM／`libpython3.12.so.1.0`／`PyUnicode_FromFormatV`。
- 时钟读取：OPM／`libc.so.6`／`clock_gettime@@GLIBC_2.17`。
- 模型／重算：TLC／`libsclo.so`／`ScColumn::GetRangeScriptType(mdds::mtv::soa::detail::iterator_base<mdds::mtv::soa::multi_type_vector<sc::CellTextAttrTraits>::iterator_trait>&, int, int, mdds::mtv::soa::detail::iterator_base<mdds::mtv::soa::multi_type_vector<sc::CellStoreTraits>::iterator_trait> const&) [clone .part.0]`。
- 正则处理：OPM／`libpython3.12.so.1.0`／`_sre_SRE_Pattern_match`。
- 线程同步／运行时支持：OPM／`libc.so.6`／`sem_post@@GLIBC_2.34`。
- 语言／区域配置：TLC／`libutllo.so`／`utl::TransliterationWrapper::compareString(rtl::OUString const&, rtl::OUString const&) const`。
- 配置读取／管理：TLC／`libconfigmgrlo.so`／`configmgr::Data::equalTemplateNames(rtl::OUString const&, rtl::OUString const&)`。

## 剩余函数审阅

下面展示各例尚未归并的主要函数，不把这些全部称为新操作；functions.csv 保留全量账本。

### 001

| 库 | 函数 | 整轮权重 |
|---|---|---|
| libfreeblpriv3.so | `s_mpv_mul_d_add_prop` | 0.131% |
| libuno_sal.so.3 | `rtl::uri::detail::readUcs4(char16_t const**, char16_t const*, bool, unsigned short, rtl::uri::detail::EscapeType*)` | 0.060% |
| libhyphenlo.so | `Hyphenator::ensureLocales()` | 0.050% |
| libc.so.6 | `__run_exit_handlers` | 0.024% |
| libsqlite3.so.0.8.6 | `sqlite3VdbeExec` | 0.001% |
| libc.so.6 | `__get_child_max` | 0.001% |
| libc.so.6 | `__GI_____strtoll_l_internal` | 0.000% |
| libc.so.6 | `__getdelim` | 0.000% |
| libc.so.6 | `__internal_atexit` | 0.000% |
| libsqlite3.so.0.8.6 | `syncJournal.part.0` | 0.000% |
| libuno_sal.so.3 | `ChildStatusProc` | 0.000% |
| libc.so.6 | `sched_setaffinity@@GLIBC_2.17` | 0.000% |

### 003

| 库 | 函数 | 整轮权重 |
|---|---|---|
| libfreeblpriv3.so | `s_mpv_mul_d_add_prop` | 0.012% |
| libsfxlo.so | `SfxObjectShell::IsEnableSetModified() const` | 0.012% |
| libfreeblpriv3.so | `s_mp_add_3arg` | 0.012% |
| libtllo.so | `ZCodec::Write(SvStream&, unsigned char const*, unsigned int)` | 0.012% |
| libsvtlo.so | `BorderWidthImpl::GetGap(long) const` | 0.012% |
| libfreeblpriv3.so | `s_mpv_mul_d_add` | 0.011% |
| libicuuc.so.77 | `icu_77::RuleBasedBreakIterator::handleSafePrevious(int)` | 0.011% |
| libi18npoollo.so | `i18npool::BreakIteratorImpl::getLineBreak(rtl::OUString const&, int, com::sun::star::lang::Locale const&, int, com::sun::star::i18n::LineBreakHyphenationOptions const&, com::sun::star::i18n::LineBreakUserOptions const&)` | 0.010% |
| libcairo.so.2.11800.0 | `_cairo_pattern_create_solid` | 0.010% |
| p11-kit-trust.so | `p11_attrs_build` | 0.010% |
| libuno_cppuhelpergcc3.so.3 | `(anonymous namespace)::InterfaceTypeDescription::getBaseTypes()` | 0.010% |
| libfilterconfiglo.so | `non-virtual thunk to cppu::ImplInheritanceHelper<filter::config::BaseContainer, com::sun::star::lang::XMultiServiceFactory>::queryInterface(com::sun::star::uno::Type const&)` | 0.009% |

### 009

| 库 | 函数 | 整轮权重 |
|---|---|---|
| libvcllo.so | `vcl::PDFWriterImpl::registerSimpleGlyph(unsigned int, vcl::font::PhysicalFontFace const*, std::vector<char16_t, std::allocator<char16_t> > const&, int, unsigned char&, int&)` | 0.076% |
| libvcllo.so | `GDIMetaFile::operator=(GDIMetaFile const&)` | 0.076% |
| libsvtlo.so | `BorderWidthImpl::GetGap(long) const` | 0.073% |
| libvcllo.so | `GDIMetaFile::AddAction(rtl::Reference<MetaAction> const&)` | 0.051% |
| libvcllo.so | `GDIMetaFile::Clear()` | 0.051% |
| libvcllo.so | `vcl::PageSyncData::PushAction(OutputDevice const&, std::variant<vcl::(anonymous namespace)::EnsureStructureElement, vcl::(anonymous namespace)::InitStructureElement, vcl::(anonymous namespace)::BeginStructureElement, vcl::(anonymous namespace)::EndStructureElement, vcl::(anonymous namespace)::SetCurrentStructureElement, vcl::(anonymous namespace)::SetStructureAttribute, vcl::(anonymous namespace)::SetStructureAttributeNumerical, vcl::(anonymous namespace)::SetStructureBoundingBox, vcl::(anonymous namespace)::SetStructureAnnotIds, vcl::(anonymous namespace)::SetActualText, vcl::(anonymous namespace)::SetAlternateText, vcl::(anonymous namespace)::CreateControl, vcl::(anonymous namespace)::BeginGroup, vcl::(anonymous namespace)::EndGroupGfxLink>) [clone .isra.0]` | 0.051% |
| libfreeblpriv3.so | `s_mpv_mul_d_add` | 0.051% |
| libvcllo.so | `vcl::text::IsControlChar(unsigned int)` | 0.051% |
| p11-kit-trust.so | `lookup_or_create_bucket` | 0.049% |
| libfreeblpriv3.so | `s_mpv_mul_d_add_prop` | 0.026% |
| libuno_sal.so.3 | `int rtl::str::compare<rtl::str::with_length<char16_t const>, rtl::str::with_length<char16_t const>, rtl::str::CompareIgnoreAsciiCase, rtl::str::NoShortening>(rtl::str::with_length<char16_t const>, rtl::str::with_length<char16_t const>, rtl::str::CompareIgnoreAsciiCase, rtl::str::NoShortening) [clone .isra.0]` | 0.026% |
| libdrawinglayerlo.so | `drawinglayer::attribute::(anonymous namespace)::theGlobalDefault()` | 0.026% |

### 013

| 库 | 函数 | 整轮权重 |
|---|---|---|
| array.cpython-312-aarch64-linux-gnu.so | `i_setitem` | 0.002% |
| libvcllo.so | `vcl::(anonymous namespace)::removePlaceholderSEImpl(std::vector<vcl::pdf::PDFStructureElement, std::allocator<vcl::pdf::PDFStructureElement> >&, __gnu_cxx::__normal_iterator<int*, std::vector<int, std::allocator<int> > >&)` | 0.002% |
| libMagickCore-7.Q16HDRI.so.10.0.2 | `GetLastImageInList` | 0.002% |
| libtllo.so | `SvStream::FlushBuffer()` | 0.002% |
| libMagickCore-7.Q16HDRI.so.10.0.2 | `AcquireVirtualCacheView` | 0.002% |
| libvcllo.so | `vcl::PDFWriterImpl::registerGlyph(unsigned int, vcl::font::PhysicalFontFace const*, LogicalFontInstance const*, std::vector<char16_t, std::allocator<char16_t> > const&, int, unsigned char&, int&)` | 0.002% |
| libvcllo.so | `vcl::PageSyncData::PlaySyncPageAct(vcl::PDFWriter&, unsigned int&, GDIMetaFile const&, vcl::PDFExtOutDevData const&)` | 0.002% |
| libvcllo.so | `MapMode::~MapMode()` | 0.002% |
| libMagickCore-7.Q16HDRI.so.10.0.2 | `QueryColorCompliance` | 0.002% |
| libfreeblpriv3.so | `MD5_Update` | 0.002% |
| libMagickCore-7.Q16HDRI.so.10.0.2 | `GetResizeFilterWeight` | 0.002% |
| libMagickCore-7.Q16HDRI.so.10.0.2 | `GetQuantumExtent` | 0.002% |

### 014

| 库 | 函数 | 整轮权重 |
|---|---|---|
| libvcllo.so | `GDIMetaFile::Clear()` | 0.032% |
| libsvxcorelo.so | `drawinglayer::primitive2d::SdrFrameBorderPrimitive2D::create2DDecomposition(drawinglayer::geometry::ViewInformation2D const&) const` | 0.019% |
| libvcllo.so | `GDIMetaFile::AddAction(rtl::Reference<MetaAction> const&)` | 0.019% |
| libsvxcorelo.so | `(anonymous namespace)::StyleVectorCombination::StyleVectorCombination(svx::frame::Style const&, basegfx::B2DVector const&, double, bool, Color const*, double) [clone .isra.0]` | 0.013% |
| libvcllo.so | `GDIMetaFile::operator=(GDIMetaFile const&)` | 0.013% |
| libsvxcorelo.so | `(anonymous namespace)::getExtends(std::vector<(anonymous namespace)::ExtendSet, std::allocator<(anonymous namespace)::ExtendSet> >&, basegfx::B2DPoint const&, (anonymous namespace)::StyleVectorCombination const&, basegfx::B2DVector const&, std::vector<(anonymous namespace)::StyleVectorCombination, std::allocator<(anonymous namespace)::StyleVectorCombination> > const&)` | 0.013% |
| libvcllo.so | `vcl::PDFWriterImpl::registerSimpleGlyph(unsigned int, vcl::font::PhysicalFontFace const*, std::vector<char16_t, std::allocator<char16_t> > const&, int, unsigned char&, int&)` | 0.013% |
| libvcllo.so | `MapMode::MapMode(MapMode const&)` | 0.013% |
| libsvxcorelo.so | `svx::frame::Style::hashCode() const` | 0.013% |
| libsvxcorelo.so | `svx::frame::(anonymous namespace)::Cell::hashCode() const` | 0.013% |
| libsvxcorelo.so | `svx::frame::(anonymous namespace)::Cell::operator==(svx::frame::(anonymous namespace)::Cell const&) const` | 0.013% |
| libfreeblpriv3.so | `md5_compress` | 0.012% |

### 016

| 库 | 函数 | 整轮权重 |
|---|---|---|
| libsvxcorelo.so | `drawinglayer::primitive2d::SdrFrameBorderData::create2DDecomposition(drawinglayer::primitive2d::Primitive2DContainer&, double) const` | 0.147% |
| libtllo.so | `tools::Polygon::Polygon(tools::Polygon const&)` | 0.139% |
| libvcllo.so | `GetLocalizedChar(unsigned int, o3tl::strong_int<unsigned short, LanguageTypeTag>)` | 0.138% |
| libsvxcorelo.so | `drawinglayer::primitive2d::SdrFrameBorderPrimitive2D::create2DDecomposition(drawinglayer::geometry::ViewInformation2D const&) const` | 0.138% |
| libfreeblpriv3.so | `md5_compress` | 0.136% |
| libtasn1.so.6.6.3 | `asn1_der_decoding2` | 0.121% |
| p11-kit-trust.so | `lookup_or_create_bucket` | 0.121% |
| libtllo.so | `DateTime::DateTime(DateTime::DateTimeInitSystem)` | 0.120% |
| libuno_sal.so.3 | `void rtl::str::doubleToString<_rtl_uString>(_rtl_uString**, int*, int, double, rtl_math_StringFormat, int, std::remove_extent<decltype (_rtl_uString::buffer)>::type, int const*, std::remove_extent<decltype (_rtl_uString::buffer)>::type, bool)` | 0.003% |
| bash | `buffered_getchar` | 0.002% |
| ld-linux-aarch64.so.1 | `memcpy` | 0.002% |
| libc.so.6 | `getpwuid` | 0.001% |

### 021

| 库 | 函数 | 整轮权重 |
|---|---|---|
| libooxlo.so | `oox::core::FilterBase::getGraphicHelper() const` | 0.061% |
| libicuuc.so.77 | `ubidi_getCustomizedClass_77` | 0.061% |
| libsvxcorelo.so | `boost::spirit::classic::impl::concrete_parser<boost::spirit::classic::contiguous<boost::spirit::classic::positive<boost::spirit::classic::alternative<boost::spirit::classic::alternative<boost::spirit::classic::range<char>, boost::spirit::classic::range<char> >, boost::spirit::classic::range<char> > > >, boost::spirit::classic::scanner<char const*, boost::spirit::classic::scanner_policies<boost::spirit::classic::skipper_iteration_policy<boost::spirit::classic::iteration_policy>, boost::spirit::classic::match_policy, boost::spirit::classic::action_policy> >, boost::spirit::classic::nil_t>::do_parse_virtual(boost::spirit::classic::scanner<char const*, boost::spirit::classic::scanner_policies<boost::spirit::classic::skipper_iteration_policy<boost::spirit::classic::iteration_policy>, boost::spirit::classic::match_policy, boost::spirit::classic::action_policy> > const&) const` | 0.061% |
| libsdlo.so | `SdDrawDocument::SetChanged(bool)` | 0.060% |
| libutllo.so | `char const* boost::locale::gnu_gettext::runtime_conversion<char>(char const*, std::__cxx11::basic_string<char, std::char_traits<char>, std::allocator<char> >&, bool, std::__cxx11::basic_string<char, std::char_traits<char>, std::allocator<char> > const&, std::__cxx11::basic_string<char, std::char_traits<char>, std::allocator<char> > const&)` | 0.060% |
| libsfxlo.so | `SfxObjectShell::IsEnableSetModified() const` | 0.059% |
| libsvxcorelo.so | `SdrEdgeObj::NbcSetSnapRect(tools::Rectangle const&)` | 0.058% |
| libsfxlo.so | `SfxApplication::GetModule(SfxToolsModule)` | 0.058% |
| libsvxcorelo.so | `SdrObject::getUnoShape()` | 0.058% |
| libsvxcorelo.so | `sdr::table::TableLayouter::SetBorder(int, int, bool, editeng::SvxBorderLine const*)` | 0.057% |
| libvcllo.so | `lang_find_or_insert(char const*)` | 0.057% |
| libsvxcorelo.so | `SdrMakeOutliner(OutlinerMode, SdrModel&)` | 0.057% |

### 026

| 库 | 函数 | 整轮权重 |
|---|---|---|
| libsdlo.so | `SdXImpressDocument::create(rtl::OUString const&, rtl::OUString const&)` | 0.109% |
| libsvxcorelo.so | `SdrCustomShapeGeometryItem::ItemType() const` | 0.107% |
| libicuuc.so.77 | `getDirProps(UBiDi*)` | 0.106% |
| libfreeblpriv3.so | `s_mpv_mul_d_add` | 0.104% |
| libooxlo.so | `(anonymous namespace)::lcl_parsePathCoordinateValues(std::vector<com::sun::star::beans::PropertyValue, std::allocator<com::sun::star::beans::PropertyValue> >&, std::basic_string_view<char, std::char_traits<char> >)` | 0.096% |
| libutllo.so | `boost::locale::basic_message<char>::write(std::locale const&, int, std::__cxx11::basic_string<char, std::char_traits<char>, std::allocator<char> >&) const` | 0.022% |
| libfreeblpriv3.so | `md5_compress` | 0.020% |
| libvcllo.so | `vcl::PageSyncData::PushAction(OutputDevice const&, std::variant<vcl::(anonymous namespace)::EnsureStructureElement, vcl::(anonymous namespace)::InitStructureElement, vcl::(anonymous namespace)::BeginStructureElement, vcl::(anonymous namespace)::EndStructureElement, vcl::(anonymous namespace)::SetCurrentStructureElement, vcl::(anonymous namespace)::SetStructureAttribute, vcl::(anonymous namespace)::SetStructureAttributeNumerical, vcl::(anonymous namespace)::SetStructureBoundingBox, vcl::(anonymous namespace)::SetStructureAnnotIds, vcl::(anonymous namespace)::SetActualText, vcl::(anonymous namespace)::SetAlternateText, vcl::(anonymous namespace)::CreateControl, vcl::(anonymous namespace)::BeginGroup, vcl::(anonymous namespace)::EndGroupGfxLink>) [clone .isra.0]` | 0.004% |
| libvcllo.so | `(anonymous namespace)::BlurTask::~BlurTask()` | 0.003% |
| libicuuc.so.77 | `icu_77::RuleBasedBreakIterator::handleNext()` | 0.003% |
| libvcllo.so | `SvpSalGraphics::~SvpSalGraphics()` | 0.003% |
| libvcllo.so | `(anonymous namespace)::BlurArrays::BlurArrays((anonymous namespace)::BlurSharedData const&)` | 0.003% |

### 029

| 库 | 函数 | 整轮权重 |
|---|---|---|
| libsdlo.so | `SdXShape::SdXShape(SvxShape*, SdXImpressDocument*)` | 0.389% |
| libicuuc.so.77 | `ubidi_getCustomizedClass_77` | 0.386% |
| libsvllo.so | `svl::undo::impl::UndoManagerGuard::~UndoManagerGuard()` | 0.364% |
| libsvxcorelo.so | `XFillColorItem::PutValue(com::sun::star::uno::Any const&, unsigned char)` | 0.364% |
| libcomphelper.so | `comphelper::(anonymous namespace)::hashValue(unsigned long, void const*, _typelib_TypeDescriptionReference*)` | 0.364% |
| libsvxcorelo.so | `SdrTextFitToSizeTypeItem::PutValue(com::sun::star::uno::Any const&, unsigned char)` | 0.362% |
| libsvxcorelo.so | `sdr::table::Cell::setPropertyValue(rtl::OUString const&, com::sun::star::uno::Any const&)` | 0.360% |
| libicuuc.so.77 | `ubidi_getLogicalRun_77` | 0.356% |
| libsvxcorelo.so | `non-virtual thunk to sdr::table::TableModel::setModified(unsigned char)` | 0.351% |
| libfreeblpriv3.so | `s_mpv_mul_d_add` | 0.344% |
| libm.so.6 | `__sin` | 0.134% |
| libvcllo.so | `Bitmap::ImplMakeGreyscales()` | 0.076% |

### 031

| 库 | 函数 | 整轮权重 |
|---|---|---|
| bash | `set_login_shell` | 0.001% |
| libc.so.6 | `sched_setaffinity@@GLIBC_2.17` | 0.000% |

### 037

| 库 | 函数 | 整轮权重 |
|---|---|---|
| libc.so.6 | `name_to_database_index` | 0.001% |
| bash | `tilde_initialize` | 0.001% |
| libc.so.6 | `sched_setaffinity@@GLIBC_2.17` | 0.000% |

### pdfwf005

| 库 | 函数 | 整轮权重 |
|---|---|---|
| libMagickCore-7.Q16HDRI.so.10.0.2 | `GetImageOption` | 0.095% |
| libMagickCore-7.Q16HDRI.so.10.0.2 | `GetDrawInfo` | 0.094% |
| libMagickCore-7.Q16HDRI.so.10.0.2 | `GetLastImageInList` | 0.094% |
| libMagickWand-7.Q16HDRI.so.10.0.2 | `MogrifyImageInfo` | 0.093% |
| bash | `phash_create` | 0.001% |
| bash | `coproc_pidchk` | 0.001% |
| bash | `get_working_directory` | 0.001% |
| bash | `find_variable_tempenv` | 0.000% |
| libc.so.6 | `sched_setaffinity@@GLIBC_2.17` | 0.000% |
