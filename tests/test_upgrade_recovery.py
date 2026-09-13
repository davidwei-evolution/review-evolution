"""Regressions from a real-machine upgrade (2026-09-12): U1/U5/U6/U7/U10 plus U8/U9.

U1 is the important one: a client's upload/register path rewrote the installed SKILL.md
(`description: >` became `description: |`, plus an injected `install_method: upload`), which
broke the manifest check and blocked the upgrade at step one - with a one-line error and no
way forward. These tests pin the actionable error, the read-only `diff` diagnosis, the
receipt template, the split update-check status, and the capability-change report.
"""
from pathlib import Path
import json,re,subprocess,sys,tempfile,unittest

CORE=Path(__file__).resolve().parents[1]
sys.path.insert(0,str(CORE/'scripts'))
sys.path.insert(0,str(CORE/'tests'))
from test_components import optional_s3_enabled   # noqa: E402  (edition-aware assertions)
import core_package as cp
import diagnostics as dg
import experience as e
import profile_backup as pb
import release_gate as gate
import release_update as u
import safe_store as st


class CorePair(unittest.TestCase):
    """A clone of the real core, so the fixtures keep the real file inventory."""

    def setUp(self):
        self.tmp=tempfile.TemporaryDirectory();self.root=Path(self.tmp.name)
        self.target=self.root/'skills'/'review-evolution'
        self.candidate=self.root/'candidate'
        self.reference=self.root/'reference'
        self.clone(self.target,'0.11.0');self.clone(self.reference,'0.11.0')
        self.clone(self.candidate,'0.12.0')

    def tearDown(self):
        self.tmp.cleanup()

    def clone(self,path,version,s3_available=None):
        """s3_available=None keeps the shipped runtime policy; pass True/False to force one.
        The capability test must set it explicitly, otherwise the fixture inherits whichever
        edition this copy of the core is (dev core: S3 on; public candidate: S3 off)."""
        meta,payload=u.core_bytes(u.CORE)
        for rel,data in payload.items():
            st.atomic_bytes(st.inside(path,rel),data)
        meta['version']=version
        if s3_available is not None:
            policy=st.json_bytes({'schema':1,
                                  'edition':'development' if s3_available else 'public',
                                  's3_available':bool(s3_available)})
            st.atomic_bytes(path/'runtime-policy.json',policy)
            meta['files']['runtime-policy.json']=st.digest(policy)
        st.atomic_bytes(path/'CORE.json',st.json_bytes(meta))

    def add_file(self,root,rel,data):
        meta=u.parse_json((root/'CORE.json').read_bytes())
        st.atomic_bytes(st.inside(root,rel),data)
        meta['files'][rel]=st.digest(data)
        st.atomic_bytes(root/'CORE.json',st.json_bytes(meta))

    def host_rewrite(self,path):
        """Reproduce what the client's upload path did to SKILL.md."""
        skill=path/'SKILL.md'
        text=skill.read_text(encoding='utf-8').replace('description: >','description: |',1)
        lines=text.split('\n')
        close=lines.index('---',1)
        lines.insert(close,'install_method: upload')
        skill.write_text('\n'.join(lines),encoding='utf-8')

    def host_flatten(self,path):
        """The harsher variant seen on the real machine: the block scalar was not only marked
        differently but **flattened into one long line**, so the first ASCII colon sits far to
        the right and naive parsing reports a paragraph as a key name."""
        skill=path/'SKILL.md'
        lines=skill.read_text(encoding='utf-8').split('\n')
        close=lines.index('---',1)
        head=lines[1:close];body=lines[close:]
        merged=[]
        for line in head:
            if line.startswith((' ','\t')) and merged:
                merged[-1]=merged[-1]+line.strip()
            else:
                merged.append(line)
        merged=[line.replace('description: >','description: |',1) for line in merged]
        skill.write_text('\n'.join(['---',*merged,*body]),encoding='utf-8')

    def cli(self,*args):
        return subprocess.run([sys.executable,'-B',str(CORE/'scripts'/'release_update.py'),*args],
                              capture_output=True,encoding='utf-8',errors='replace',timeout=120)


class HostRewriteBlockedUpgrade(CorePair):
    def test_verify_names_the_file_and_the_way_out(self):
        self.host_rewrite(self.target)
        with self.assertRaises(ValueError) as ctx:
            cp.verify(self.target)
        message=str(ctx.exception)
        self.assertIn('Core content mismatch: SKILL.md',message)
        self.assertIn('不要修改 CORE.json',message)
        self.assertIn('core_package.py diff',message)

    def test_diff_classifies_a_frontmatter_only_rewrite(self):
        self.host_rewrite(self.target)
        report=cp.diff(self.target,self.reference)
        self.assertEqual(report['status'],'MISMATCH')
        self.assertEqual([row['file'] for row in report['differences']],['SKILL.md'])
        row=report['differences'][0]
        self.assertEqual(row['kind'],'frontmatter-only')
        self.assertIn('install_method',row['keys_added'])
        self.assertIn('不要修改 CORE.json',report['next_step'])

    def test_diff_without_a_reference_still_points_at_the_file(self):
        self.host_rewrite(self.target)
        row=cp.diff(self.target)['differences'][0]
        self.assertEqual(row['kind'],'unknown-needs-reference')
        self.assertTrue(row['likely_frontmatter_edited'])

    def test_diff_on_a_clean_core_is_a_match(self):
        report=cp.diff(self.reference)
        self.assertEqual(report['status'],'MATCH')
        self.assertEqual(report['differences'],[])
        self.assertEqual(report['extra_files'],[])

    def test_install_plan_keeps_the_stable_wording_and_adds_the_recovery_path(self):
        self.host_rewrite(self.target)
        with self.assertRaises(ValueError) as ctx:
            u.install_plan(self.candidate,self.target,True,'0.12.0')
        message=str(ctx.exception)
        self.assertIn('Target core invalid',message)
        self.assertIn('用同版本原包',message)

    def test_broken_local_core_is_not_reported_as_a_publishing_problem(self):
        self.host_rewrite(self.target)
        result=u.check(self.target)
        self.assertEqual(result['status'],'LOCAL_CORE_INVALID')
        self.assertIn('与发布源无关',result['message'])
        self.assertIn('diff --root',result['next_step'])


class HostRewriteRepair(CorePair):
    """W1 (2026-09-13)：被宿主改写的目标核心，可用候选包同名官方文件修复后继续升级。

    默认行为不变（仍然拒绝）；只有显式 repair_host_rewrite 才继续，且结束后必须整目录核验通过。
    """

    def test_default_still_refuses(self):
        self.host_rewrite(self.target)
        with self.assertRaises(ValueError) as ctx:
            u.install_plan(self.candidate,self.target,True,'0.12.0')
        self.assertIn('Target core invalid',str(ctx.exception))

    def test_repair_plan_marks_the_file_and_install_restores_official_bytes(self):
        self.host_rewrite(self.target)
        plan=u.install_plan(self.candidate,self.target,True,'0.12.0',repair_host_rewrite=True)
        self.assertEqual(sorted(plan['repair']['files']),['SKILL.md'])
        self.assertTrue(plan['changes']['SKILL.md']['host_rewrite_repair'])
        result=u.install(self.candidate,self.target,plan['plan_id'],True,'0.12.0',
                         repair_host_rewrite=True)
        self.assertEqual(result['status'],'UPDATED')
        self.assertIn('候选包中的同名官方文件',result['message'])
        self.assertEqual(cp.verify(self.target)['version'],'0.12.0')
        self.assertEqual(st.hash_file(self.target/'SKILL.md'),st.hash_file(self.candidate/'SKILL.md'))

    def test_repair_consent_is_bound_to_the_plan(self):
        self.host_rewrite(self.target)
        plan=u.install_plan(self.candidate,self.target,True,'0.12.0',repair_host_rewrite=True)
        with self.assertRaises(ValueError) as ctx:
            u.install(self.candidate,self.target,plan['plan_id'],True,'0.12.0')
        self.assertIn('Target core invalid',str(ctx.exception))

    def test_clean_target_is_unaffected_by_the_flag(self):
        plan=u.install_plan(self.candidate,self.target,True,'0.12.0',repair_host_rewrite=True)
        self.assertIsNone(plan['repair'])
        self.assertNotIn('host_rewrite_repair',json.dumps(plan['changes']))


class ReceiptTemplate(CorePair):
    def test_template_fills_hashes_and_only_needs_reviewer_and_reason(self):
        self.add_file(self.candidate,'references/added-helper.md',b'# synthetic helper\n')
        out=self.root/'receipt.json'
        result=u.emit_receipt_template(self.candidate,self.target,out)
        self.assertEqual(result['status'],'WROTE_TEMPLATE')
        self.assertEqual(result['files'],['references/added-helper.md'])
        row=json.loads(out.read_text(encoding='utf-8'))
        self.assertEqual(row['purpose'],'component-review')
        self.assertEqual(row['version'],'0.12.0')
        self.assertEqual(row['reviewed_by'],'')
        meta=u.parse_json((self.candidate/'CORE.json').read_bytes())
        self.assertEqual(row['files']['references/added-helper.md'],
                         meta['files']['references/added-helper.md'])

    def test_template_refuses_to_overwrite_or_write_inside_a_core(self):
        out=self.root/'receipt.json';out.write_text('{}',encoding='utf-8')
        with self.assertRaises(ValueError):u.emit_receipt_template(self.candidate,self.target,out)
        with self.assertRaises(ValueError):
            u.emit_receipt_template(self.candidate,self.target,self.candidate/'inner.json')

    def test_receipt_round_trips_into_install_plan(self):
        self.add_file(self.candidate,'references/added-helper.md',b'# synthetic helper\n')
        out=self.root/'receipt.json'
        u.emit_receipt_template(self.candidate,self.target,out)
        row=json.loads(out.read_text(encoding='utf-8'))
        row['reviewed_by']='acceptance test';row['reason']='synthetic public test content'
        out.write_text(json.dumps(row,ensure_ascii=False),encoding='utf-8')
        plan=u.install_plan(self.candidate,self.target,True,'0.12.0',out)
        self.assertEqual(plan['component_review']['files'],['references/added-helper.md'])


class CliCompatibility(CorePair):
    def test_candidate_may_be_passed_as_an_option(self):
        proc=self.cli('plan-install','--candidate',str(self.candidate),'--target',str(self.target),
                      '--expected-version','0.12.0','--allow-dev')
        self.assertEqual(0,proc.returncode,proc.stderr+proc.stdout)
        self.assertIn('plan_id',json.loads(proc.stdout))

    def test_missing_candidate_errors_with_guidance(self):
        proc=self.cli('plan-install','--target',str(self.target),'--expected-version','0.12.0','--allow-dev')
        self.assertNotEqual(0,proc.returncode)
        message=proc.stderr+proc.stdout
        self.assertIn('二选一',message)
        self.assertIn('CLI 参数变更记录',message)


class CapabilityChangeReported(CorePair):
    def test_public_candidate_reports_the_loss_of_the_optional_module(self):
        self.clone(self.target,'0.11.0',s3_available=True)
        self.clone(self.candidate,'0.12.0',s3_available=False)
        plan=u.install_plan(self.candidate,self.target,True,'0.12.0')
        self.assertEqual(plan['edition'],'public')
        self.assertFalse(plan['s3_available'])
        self.assertIsNotNone(plan['capability_change'])
        # 2026-09-13：提示语不再出现内部模块名（用户侧零痕迹），改为中性的“发行形态不同”。
        note=plan['capability_change']['note']
        self.assertIn('发行形态',note);self.assertNotIn('S3',note)
        result=u.install(self.candidate,self.target,plan['plan_id'],True,'0.12.0')
        self.assertEqual(result['edition'],'public')
        self.assertIn('发行形态',result['message']);self.assertNotIn('S3',result['message'])

    def test_no_capability_change_is_reported_when_the_module_stays(self):
        self.clone(self.target,'0.11.0',s3_available=True)
        self.clone(self.candidate,'0.12.0',s3_available=True)
        plan=u.install_plan(self.candidate,self.target,True,'0.12.0')
        self.assertIsNone(plan['capability_change'])
        self.assertTrue(plan['s3_available'])


class SmallFixes(CorePair):
    def test_intro_cards_speak_plain_language_only(self):
        """2026-09-12 用户反馈：生成的自我介绍里出现了 recall/query、add/add-event、doctor。
        根因是 intro 的能力卡片自带内部命令名。用户可见的三个字段必须零技术词。"""
        import experience as e
        forbidden=re.compile(r'(?i)\b(recall|query|add|add-event|doctor|intro|observe-s1|observe-s2|'
                             r's1-metrics|s2-metrics|log-s3|query-s3|s3-record|s3-classify|backup|restore|'
                             r'export|import|scenario|legacy-search)\b|SKILL\.md|experience\.py|JSON|CORE'
                             r'|（S1）|（S2）|（S3）|S1|S2|S3')
        cards=e.introduction(core=CORE)['capabilities']
        self.assertTrue(cards)
        for card in cards:
            for field in ('ability','example','advice'):
                text=card[field]
                self.assertIsNone(forbidden.search(text),
                                  'card %s field %s 含技术词：%s' % (card['id'],field,text))
            self.assertNotIn('commands',card,'内部命令名不应出现在给 AI 的能力事实里')

    def test_intro_tells_the_agent_not_to_read_out_internal_ids(self):
        import experience as e
        composition=e.introduction(core=CORE)['composition']
        self.assertIn('plain_language',composition)
        self.assertIn('不得出现',composition['plain_language'])
        self.assertIn('不要念给用户',composition['plain_language'])
        skill=(CORE/'SKILL.md').read_text(encoding='utf-8')
        self.assertIn('零技术词',skill)
        self.assertIn('recall/query',skill)   # 反例本身要留在规则里，作为对照
        # 发现面（description）也不该带内部代号——模型会把它们照搬进自我介绍
        from test_skill_metadata import read_frontmatter
        description=read_frontmatter(CORE/'SKILL.md')['description']
        self.assertIsNone(re.search(r'S1|S2|S3',description),
                          'description 里不应出现 S1/S2/S3 这类内部代号')

    def test_intro_language_rule_is_a_hard_requirement(self):
        """多语言（2026-09-12 用户确认加固）：必须是规则，不是"建议"。"""
        import experience as e
        language=e.introduction(core=CORE)['composition']['language']
        self.assertIn('必须使用用户当前使用的语言',language)
        self.assertIn('不要中英混排',language)
        self.assertIn('answer entirely in that language',language)
        skill=(CORE/'SKILL.md').read_text(encoding='utf-8')
        self.assertIn('语言硬要求',skill)
        public=CORE/'scripts'/'build_public.py'
        if public.is_file():   # 公开候选里没有构建脚本
            self.assertIn('语言硬要求',public.read_text(encoding='utf-8'))

    def test_host_rewrite_guidance_is_printed_only_once(self):
        """N1: verify() already appends the hint; checked_core() must not add it again."""
        self.host_rewrite(self.target)
        with self.assertRaises(ValueError) as ctx:
            u.install_plan(self.candidate,self.target,True,'0.12.0')
        self.assertEqual(str(ctx.exception).count(cp.HOST_REWRITE_HINT),1)

    def test_frontmatter_key_parse_ignores_flattened_paragraphs(self):
        """N2: a flattened host rewrite put a whole Chinese paragraph on the description line;
        the old parser reported it as a key name."""
        probe=self.root/'probe.md'
        probe.write_text('---\nname: x\ndescription: |\n  '
                         'Search tags: 经验复盘、长期记忆；First-run onboarding: 一段中文说明\n'
                         'install_method: upload\n---\nbody\n',encoding='utf-8')
        facts=cp._file_facts(probe)
        self.assertEqual(facts['facts']['frontmatter_keys'],['name','description','install_method'])
        for key in facts['facts']['frontmatter_keys']:
            self.assertLess(len(key),40,key)

    def test_flattened_rewrite_keeps_keys_added_and_removed_clean(self):
        """N2 second half: keys_added/keys_removed must use the same strict filter.
        Reported on a real machine: keys_added held a 355-character Chinese paragraph."""
        self.host_flatten(self.target)
        report=cp.diff(self.target,self.reference)
        self.assertEqual(report['status'],'MISMATCH')
        row=report['differences'][0]
        self.assertEqual(row['kind'],'frontmatter-only')
        for label in ('keys_added','keys_removed'):
            keys=row.get(label) or []
            for key in keys:
                self.assertRegex(key,r'^[A-Za-z_][A-Za-z0-9_-]*$',label+' -> '+key[:40])
                self.assertLess(len(key),40,label)
        # 键名没变、只是表示法被压平 → 两个集合都应为空；真正变化记在 block style/值上。
        self.assertEqual(row.get('keys_added'),[])

    def test_local_core_invalid_does_not_ask_for_an_online_recheck(self):
        """N3: 'do not retry online' must not ship with cross_check=true/ releases_page."""
        self.host_rewrite(self.target)
        result=u.check(self.target)
        self.assertEqual(result['status'],'LOCAL_CORE_INVALID')
        self.assertFalse(result['cross_check'])
        self.assertNotIn('releases_page',result)
        self.assertIn('联网复核无关',result['cross_check_reason'])

    def test_allow_dev_explanation_is_near_the_top_of_the_install_doc(self):
        """U4: the note existed but sat far down the file; a reader never reached it."""
        lines=(CORE/'references'/'install.md').read_text(encoding='utf-8').splitlines()
        head='\n'.join(lines[:40])
        self.assertIn('--allow-dev',head)
        self.assertIn('不是质量背书',head)

    def test_host_memory_rule_is_written_for_both_surfaces(self):
        """A: default dual-write must be visible in the body AND in the discovery surface."""
        body=(CORE/'SKILL.md').read_text(encoding='utf-8')
        # 正文标题的措辞在两种发行形态下可以不同（公开版正文由 build_public 重写），
        # 所以断言规则本身，而不是标题文字。
        self.assertIn('默认双写',body)
        self.assertIn('只让宿主记',body)
        from test_skill_metadata import read_frontmatter
        self.assertIn('默认双写',read_frontmatter(CORE/'SKILL.md')['description'])
        host_path=CORE/'references'/'host-integration.md'
        if not host_path.exists():
            # Public packages keep the user-facing dual-write rule, but do not ship
            # maintainer guidance written for host integrators.
            return
        host=host_path.read_text(encoding='utf-8')
        self.assertIn('默认双写',host)

    def test_backup_error_suggests_a_new_directory_name(self):
        profile=self.root/'profile';e.init(profile)
        plan=pb.backup_plan(profile)
        out=self.root/'backup';out.mkdir()
        with self.assertRaises(ValueError) as ctx:
            pb.backup(profile,out,plan['plan_id'])
        self.assertIn('带时间戳',str(ctx.exception))

    def test_doctor_reports_modules_and_all_local_installations(self):
        report=dg.doctor(core=CORE)
        # 2026-09-13（真机反馈 F2）：公开形态不再输出该板块（连键名都不出现）；开发形态保留。
        if optional_s3_enabled():
            self.assertIn('optional_modules',report)
        else:
            self.assertNotIn('optional_modules',report)
        self.assertIn('installations',report)
        self.assertGreaterEqual(report['installations']['count'],1)
        self.assertTrue(report['installations']['read_only'])

    def test_tests_package_marker_is_shipped_and_allowed(self):
        self.assertTrue((CORE/'tests'/'__init__.py').is_file())
        self.assertTrue(gate.permitted('tests/__init__.py'))


if __name__=='__main__':
    unittest.main()
