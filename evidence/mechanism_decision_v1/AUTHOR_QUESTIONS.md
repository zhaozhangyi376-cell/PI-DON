# 给作者的最小澄清问题（尚未发送）

本轮不代表用户发送任何外部消息。若本地有限验证仍无法区分实现歧义，可将下列问题与本目录的`protocol.json`、`path_check_raw.json`和失败摘要一并提供给作者。

1. IV-A式(7)实际优化的是逐项平方和、均方、相对误差还是归一化后的量？文中`1e-4`对应哪种量？
2. III-B所说“output normalized by the local maximum for each component”在未见测试场和第二阶段中怎样恢复物理量？
3. trunk的“coordinates ... providing information on cell sizes”是节点坐标、归一化坐标、常量cell-size通道，还是其他编码？
4. 在每个时间步，E与H的DCO是否共享权重、Adam状态和训练顺序？内层学习率、更新上限与停止实现是什么？
5. IV-B的evaluation stage和后续材料/几何测试使用哪一份训练后参数：最终权重、各时间层权重、再适配权重，或其他程序？

还应附注：本文实现采用标准Yee curl；印刷版式(7)的x分量符号与另两分量不一致，需确认是否仅为排版问题。
