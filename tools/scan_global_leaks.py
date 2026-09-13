#!/usr/bin/env python3
"""
tools/scan_global_leaks.py
==========================
Global scope and module-level leak detector for aux-addon.
Understands aux's custom module/package architecture:
  - Recognizes module environments (module 'aux.*') and exports (M.<export>).
  - Verifies local declarations, function parameters, loop iterators.
  - Whitelists legitimate WoW 1.12.1 C APIs and Lua 5.0 globals.
  - Detects accidental global leaks and uninitialized assignments.
"""

import os
import re
import sys

if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
ADDON_DIR = os.path.abspath(os.path.join(SCRIPT_DIR, ".."))

WOW_AND_LUA_GLOBALS = {
    # Lua 5.0 core globals
    'print', 'type', 'tostring', 'tonumber', 'pairs', 'ipairs', 'next', 'unpack',
    'pcall', 'xpcall', 'assert', 'error', 'setmetatable', 'getmetatable', 'getfenv',
    'setfenv', 'string', 'table', 'math', 'io', 'os', 'coroutine', 'table.getn', 'getn',
    'tinsert', 'tremove', 'sort', 'wipe', 'format', 'gsub', 'strfind', 'strsub',
    'strlen', 'strlower', 'strupper', 'strrep', 'mod', 'min', 'max', 'floor', 'ceil', 'abs',
    'date', 'time',

    # WoW 1.12.1 client APIs & Frame globals
    'SlashCmdList', 'CreateFrame', 'UIParent', 'Minimap', 'GameTooltip', 'message',
    'this', 'arg1', 'arg2', 'arg3', 'arg4', 'arg5', 'arg6', 'arg7', 'arg8', 'arg9',
    'event', 'DEFAULT_CHAT_FRAME', 'ChatFrame1', 'UIErrorsFrame', 'PlaySoundFile',
    'PlaySound', 'GetTime', 'GetCVar', 'SetCVar', 'UnitName', 'UnitFactionGroup',
    'GetMoney', 'PlaceAuctionBid', 'CancelAuction', 'GetOwnerAuctionItems', 'AuctionFrame',
    'AuctionFrameAuctions', 'ShowUIPanel', 'HideUIPanel', 'CloseDropDownMenus',
    'GetItemInfo', 'GetItemQualityColor', 'GetAuctionItemInfo', 'GetLootSlotInfo',
    'GetQuestItemInfo', 'GetQuestLogRewardInfo', 'GetContainerItemInfo', 'GetMerchantItemInfo',
    'GetCraftReagentItemLink', 'GetCraftReagentInfo', 'GetTradeSkillReagentItemLink',
    'GetTradeSkillReagentInfo', 'IsShiftKeyDown', 'IsControlKeyDown', 'IsAltKeyDown',
    'ClickAuctionSellItemButton', 'ClearCursor', 'PickupContainerItem', 'GetContainerItemLink',
    'GetAuctionItemLink', 'CanSendAuctionQuery', 'QueryAuctionItems', 'GetNumAuctionItems',
    'SetSelectedAuctionItem', 'GetAuctionItemTimeLeft', 'CalculateAuctionDeposit',
    'PostAuction', 'GetInboxNumItems', 'GetInboxItem', 'GetInboxText', 'TakeInboxItem',
    'TakeInboxMoney', 'AutoLootMailItem', 'GetSendMailItem', 'SendMail', 'CheckInteractDistance',
    'TargetUnit', 'TargetLastTarget', 'AssistUnit', 'CastSpellByName', 'DressUpItemLink',
    'ChatFrameEditBox', 'ItemRefTooltip', 'GameTooltip_SetDefaultAnchor', 'StartAuction',
    'GetContainerNumSlots', 'GetInventoryItemLink', 'GetChannelName', 'JoinChannelByName',
    'GetChannelList', 'UIDropDownMenu_GetSelectedValue',

    # Font colors & UI Constants
    'LIGHTYELLOW_FONT_COLOR_CODE', 'RED_FONT_COLOR_CODE', 'GREEN_FONT_COLOR_CODE',
    'FONT_COLOR_CODE_CLOSE', 'HIGHLIGHT_FONT_COLOR_CODE', 'GRAY_FONT_COLOR_CODE',
    'ERR_AUCTION_BID_PLACED', 'ERR_AUCTION_REMOVED', 'ERR_AUCTION_STARTED',
    'AUCTION_TIME_LEFT1', 'AUCTION_TIME_LEFT2', 'AUCTION_TIME_LEFT3', 'AUCTION_TIME_LEFT4',

    # Third-party / Optional libs
    'ChatThrottleLib', 'ShaguTweaks',

    # Aux system & entry globals, Blizzard hooks, CTL hooks
    'aux', 'BINDING_HEADER_AUX', 'post_auctions_bind', 'module', 'require', 'pass',
    '_G', '_M', 'M', 'AuctionFrameAuctions_OnEvent', 'SetTooltipMoney',
    'SendChatMessage', 'SendAddonMessage', 'SendAddOnMessage'
}

def collect_module_scope_vars():
    """
    Collects package-level variables shared across files declaring the same module.
    For instance, frame.lua files initialize UI components in top-level 'do ... end' blocks
    that core.lua accesses (e.g. search_box, status_bar, tabs).
    """
    module_vars = {}
    for root, _, files in os.walk(ADDON_DIR):
        if "tools" in root or ".git" in root:
            continue
        for f in files:
            if f.endswith('.lua'):
                p = os.path.join(root, f)
                with open(p, 'r', encoding='utf-8', errors='ignore') as fh:
                    lines = fh.readlines()

                mod_m = re.search(r"module\s+['\"]([^'\"]+)['\"]", "".join(lines))
                mod_name = mod_m.group(1) if mod_m else "global"
                if mod_name not in module_vars:
                    module_vars[mod_name] = set()

                in_fn = 0
                for line in lines:
                    clean = line.split('--')[0]
                    # Track whether we are inside a function
                    in_fn += len(re.findall(r'\bfunction\b', clean))
                    in_fn -= len(re.findall(r'\bend\b', clean))
                    if in_fn <= 0:
                        in_fn = 0
                        # Match assignment: var = ...
                        m = re.search(r'(?:^|\s+)([A-Za-z_][A-Za-z0-9_]*)\s*=(?!=)', clean)
                        if m:
                            var = m.group(1)
                            if var not in ('local', 'function', 'if', 'return', 'and', 'or'):
                                module_vars[mod_name].add(var)
                        m_fn = re.match(r'^function\s+([A-Za-z_][A-Za-z0-9_]*)\s*\(', clean)
                        if m_fn:
                            module_vars[mod_name].add(m_fn.group(1))
    return module_vars

def scan_file(filepath, module_vars):
    with open(filepath, 'r', encoding='utf-8', errors='ignore') as f:
        content = f.read()

    mod_m = re.search(r"module\s+['\"]([^'\"]+)['\"]", content)
    mod_name = mod_m.group(1) if mod_m else "global"
    allowed_mod_vars = module_vars.get(mod_name, set())

    # Collect local declarations
    local_vars = set()
    for decl in re.findall(r'\blocal\s+([^=;\n]+)', content):
        decl = decl.strip()
        if not decl.startswith('function'):
            for var in decl.split(','):
                v = var.strip()
                if v and re.match(r'^[A-Za-z_][A-Za-z0-9_]*$', v):
                    local_vars.add(v)
        else:
            m = re.search(r'function\s+([A-Za-z_][A-Za-z0-9_]*)', decl)
            if m:
                local_vars.add(m.group(1))

    # Function parameters
    for p_list in re.findall(r'function\s*[A-Za-z0-9_:\.]*\s*\((.*?)\)', content):
        for p in p_list.split(','):
            p = p.strip()
            if p:
                local_vars.add(p)

    # For-loop variables
    for loop_vars in re.findall(r'\bfor\s+([A-Za-z0-9_,\s]+)\s+(?:in|=)', content):
        for v in loop_vars.split(','):
            v = v.strip()
            if v:
                local_vars.add(v)

    lines = content.splitlines()
    leaks = []
    in_table = 0
    in_function = 0

    for idx, line in enumerate(lines, start=1):
        clean = line.split('--')[0].strip()
        if not clean:
            continue

        stripped = re.sub(r'"[^"\\]*(?:\\.[^"\\]*)*"', '""', clean)
        stripped = re.sub(r"'[^'\\]*(?:\\.[^'\\]*)*'", "''", stripped)

        # Track function nesting
        in_function += len(re.findall(r'\bfunction\b', stripped))
        in_function -= len(re.findall(r'\bend\b', stripped))
        if in_function < 0:
            in_function = 0

        # Check for assignment: target = ...
        m = re.match(r'^([A-Za-z_][A-Za-z0-9_]*)\s*=(?!=)', clean)
        if m and in_table == 0:
            var = m.group(1)
            # If in function or outside module, check if properly declared
            if (var not in WOW_AND_LUA_GLOBALS and
                var not in local_vars and
                var not in allowed_mod_vars and
                not var.startswith('SLASH_') and
                not var.startswith('BINDING_') and
                not var.startswith('AUX_')):
                leaks.append((idx, var, clean))

        in_table += stripped.count('{') - stripped.count('}')
        if in_table < 0:
            in_table = 0

    return leaks

def main():
    print("=" * 65)
    print("  aux-addon Scope & Global Leak Audit")
    print("=" * 65)

    module_vars = collect_module_scope_vars()
    all_leaks = []

    lua_files = []
    for root, _, files in os.walk(ADDON_DIR):
        if "tools" in root or ".git" in root:
            continue
        for f in files:
            if f.endswith('.lua'):
                lua_files.append(os.path.join(root, f))

    for filepath in sorted(lua_files):
        rel = os.path.relpath(filepath, ADDON_DIR)
        leaks = scan_file(filepath, module_vars)
        if leaks:
            print(f"\n❌ {rel} ({len(leaks)} potential scope leak(s)):")
            for line_idx, var, stmt in leaks:
                print(f"    Line {line_idx}: '{var}' -> {stmt}")
                all_leaks.append((rel, line_idx, var))
        else:
            print(f"  ✅ {rel} (zero scope leaks)")

    print("\n" + "=" * 65)
    if all_leaks:
        print(f"Audit completed with {len(all_leaks)} scope leak(s) detected.")
        sys.exit(1)
    else:
        print(f"All {len(lua_files)} files certified clean with zero unintended global leaks!")
        sys.exit(0)

if __name__ == "__main__":
    main()
