module 'aux.util.money'

local T = require 'T'
local aux = require 'aux'

M.GOLD_TEXT = '|cffffd100g|r'
M.SILVER_TEXT = '|cff98b0e0s|r'
M.COPPER_TEXT = '|cffc8602c|r'

local COPPER_PER_GOLD = 10000
local COPPER_PER_SILVER = 100

function M.to_gsc(money)
	local gold = floor(money / COPPER_PER_GOLD)
	local silver = floor(mod(money, COPPER_PER_GOLD) / COPPER_PER_SILVER)
	local copper = mod(money, COPPER_PER_SILVER)
	return gold, silver, copper
end

function M.from_gsc(gold, silver, copper)
	return gold * COPPER_PER_GOLD + silver * COPPER_PER_SILVER + copper
end

function M.format_number(num, pad, color, default_color)
	num = format('%0' .. (pad and 2 or 0) .. 'd', num)
	if color then
		if type(color) == 'function' or type(color) == 'table' then
			return color(num)
		else
			return color .. num .. FONT_COLOR_CODE_CLOSE
		end
	elseif default_color then
		return default_color .. num .. FONT_COLOR_CODE_CLOSE
	else
		return num
	end
end

function M.to_string2(money, exact, color)
	color = color or FONT_COLOR_CODE_CLOSE

	local TEXT_NONE = '0'

	local GOLD = 'ffd100'
	local SILVER = 'e6e6e6'
	local COPPER = 'c8602c'
	local START = '|cff%s%d' .. FONT_COLOR_CODE_CLOSE
	local PART = color .. '.|cff%s%02d' .. FONT_COLOR_CODE_CLOSE
	local NONE = '|cffa0a0a0' .. TEXT_NONE .. FONT_COLOR_CODE_CLOSE

	if not exact and money >= COPPER_PER_GOLD then
		money = aux.round(money / COPPER_PER_SILVER) * COPPER_PER_SILVER
	end
	local g, s, c = to_gsc(money)

	local str = ''

	local fmt = START
	if g > 0 then
		str = str .. format(fmt, GOLD, g)
		fmt = PART
	end
	if s > 0 then
		str = str .. format(fmt, SILVER, s)
		fmt = PART
	end
	if c > 0 or str == '' then
		str = str .. format(fmt, COPPER, c)
	end

	return str
end

function M.to_string(money, pad, trim, color, no_color)
    local is_negative = money < 0
    money = abs(money)
    local gold, silver, copper = to_gsc(money)

    local gold_text, silver_text, copper_text
    local default_gold_color, default_silver_color, default_copper_color

    if no_color then
        gold_text, silver_text, copper_text = 'g', 's', 'c'
    else
        default_gold_color = '|cffffd100'
        default_silver_color = '|cff98b0e0'
        default_copper_color = '|cffc8602c'
        gold_text = default_gold_color .. 'g|r'
        silver_text = default_silver_color .. 's|r'
        copper_text = default_copper_color .. 'c|r'
    end

    local text

    if trim then
        local parts = T.temp - T.acquire()
        if gold > 0 then
            tinsert(parts, format_number(gold, false, color, default_gold_color) .. gold_text)
        end
        if silver > 0 then
            tinsert(parts, format_number(silver, pad, color, default_silver_color) .. silver_text)
        end
        if copper > 0 or (gold == 0 and silver == 0) then
            tinsert(parts, format_number(copper, pad, color, default_copper_color) .. copper_text)
        end
        text = aux.join(parts, ' ')
    else
        if gold > 0 then
            text = format_number(gold, false, color, default_gold_color) .. gold_text .. ' ' .. format_number(silver, pad, color, default_silver_color) .. silver_text .. ' ' .. format_number(copper, pad, color, default_copper_color) .. copper_text
        elseif silver > 0 then
            text = format_number(silver, false, color, default_silver_color) .. silver_text .. ' ' .. format_number(copper, pad, color, default_copper_color) .. copper_text
        else
            text = format_number(copper, false, color, default_copper_color) .. copper_text
        end
    end

    if is_negative then
        local minus = '-'
        if color then
            if type(color) == 'function' or type(color) == 'table' then
                minus = color(minus)
            else
                minus = color .. minus .. FONT_COLOR_CODE_CLOSE
            end
        end
        text = minus .. text
    end

    return text
end

function M.from_string(value)
	local number = tonumber(value)
	if number and number >= 0 then
		return number * COPPER_PER_GOLD
	end

	value = gsub(gsub(strlower(value), '|c%x%x%x%x%x%x%x%x', ''), FONT_COLOR_CODE_CLOSE, '')

	local gold = tonumber(aux.select(3, strfind(value, '(%d*%.?%d+)g')))
	local silver = tonumber(aux.select(3, strfind(value, '(%d*%.?%d+)s')))
	local copper = tonumber(aux.select(3, strfind(value, '(%d*%.?%d+)c')))
	if not gold and not silver and not copper then return end

	value = gsub(value, '%d*%.?%d+g', '', 1)
	value = gsub(value, '%d*%.?%d+s', '', 1)
	value = gsub(value, '%d*%.?%d+c', '', 1)
	if strfind(value, '%S') then return end

	return from_gsc(gold or 0, silver or 0, copper or 0)
end
