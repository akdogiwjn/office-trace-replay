# 大规模任务的同类操作归并

完整 ROI 分母保持不变：精确匹配＋同类操作＋单列操作＋其他已解析＋未解析＝100%。

同类操作：PNG 编解码、明确缩放、zlib、Poppler、可识别 Calc 路径。JPEG 单列；Python/XML 和公共框架不自动归并。

单列操作：JPEG、ImageMagick 合成、Writer/PPT 对象及布局样式。单列表示独立保留的路径，不将整组推断为新增算法。

functions.csv 保留逐函数分类；comparison.json 保留全部权重、其他工具归属、丢样及未知标记。采样权重不是总 CPU 时间。
