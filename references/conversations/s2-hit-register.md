# S2 旧入口兼容指引

跨任务防错记录位于私人 profile 的 s2/records，运行 `experience.py query --component s2`。
新命中用新记录引用旧证据，不能因一次未再犯就推断长期有效。旧登记原文可用 legacy-search
检索。不要在本核心文件追加真实记录；见 [工作流](../workflow.md)。

效果事实源：真实机会出现并收尾后，用 `observe-s2 <JSON文件路径>`（或 `-` stdin）登记
（task_id/lesson_id/opportunity/recalled/applied/recurred/evidence），
`s2-metrics [--lesson <id>]` 按不同 task_id 汇总机会/召回/采用/再犯；
avoided_candidate 需用户确认真实跨任务/会话后才能描述为“已避免”。
