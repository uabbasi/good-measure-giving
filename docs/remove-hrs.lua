-- Remove horizontal rules (---) since headings provide structure in the formal report
function HorizontalRule()
  return {}
end

-- Remove the first H1 since it duplicates the title page
local first_h1 = true
function Header(el)
  if el.level == 1 and first_h1 then
    first_h1 = false
    return {}
  end
  return el
end
