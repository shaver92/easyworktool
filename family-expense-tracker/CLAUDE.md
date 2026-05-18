<!--
 * @Author: shaver 18681575528@163.com
 * @Date: 2026-05-18 17:14:07
 * @LastEditors: shaver 18681575528@163.com
 * @LastEditTime: 2026-05-18 18:15:52
 * @FilePath: /family-expense-tracker/CLAUDE.md
 * @Description: 这是默认设置,请设置`customMade`, 打开koroFileHeader查看配置 进行设置: https://github.com/OBKoro1/koro1FileHeader/wiki/%E9%85%8D%E7%BD%A
-->
# CLAUDE.md

This file provides guidance to Claude Code when working with code in this repository.

## Project Overview

easyworktool is a Streamlit-based multi-tool application with Feishu (飞书) integration, covering attendance tracking, PDF splitting, meeting minutes, MCP applications, and more.

## Skill routing

When the user's request matches an available skill, invoke it via the Skill tool. When in doubt, invoke the skill.

Key routing rules:
- Product ideas/brainstorming → invoke /office-hours
- Strategy/scope → invoke /plan-ceo-review
- Architecture → invoke /plan-eng-review
- Design system/plan review → invoke /design-consultation or /plan-design-review
- Full review pipeline → invoke /autoplan
- Bugs/errors → invoke /investigate
- QA/testing site behavior → invoke /qa or /qa-only
- Code review/diff check → invoke /review
- Visual polish → invoke /design-review
- Ship/deploy/PR → invoke /ship or /land-and-deploy
- Save progress → invoke /context-save
- Resume context → invoke /context-restore

## Language
- 生成文档与沟通，使用中文    
- Code review，使用英文    