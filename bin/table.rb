#!/usr/bin/env ruby

require 'getoptlong'
require 'pp'
require 'sqlite3'

CONTINUATION_REGEX = / _$/
TABLE_LINE_REGEX = /^\s*\|\|/
END_OF_TABLE_REGEX = /^\s*$/
ROW_TITLE_REGEX =
  /\[\[# ([a-z][a-z0-9-]*)\]\]\[#\1-note ([A-Za-z0-9? \.\/,\?;-]+)\]/
EMPTY_CELL_REGEX = /^([~\s]*|~ \[\[# [a-z-]+\]\])$/
HEADER_CELL_REGEX = /^~ \[\[# ([a-z-]+)\]\]\[#\1-note ([^\]]+)\]$/
SUPERSECTION_CELL_REGEX = /^~ ([A-Z ]+)$/
SUPERSECTIONS = ['CORE', 'DATA STRUCTURES', 'AUXILIARY', 'TABLES',
                 'MATHEMATICS', 'STATISTICS', 'CHARTS']

# FIXME: lack of encapsulation: deconstruting the regexes
# FIXME: lack of encapsulation: rows returned from db
# FIXME: generate is used for method and function name

class DB
  def initialize(path)
    @conn = SQLite3::Database.new path
  end

  def setup
    @conn.execute("CREATE TABLE sections (
                     title text PRIMARY KEY,
                     anchor text NOT NULL,
                     position integer NOT NULL,
                     supersection text NOT NULL,
                     CONSTRAINT pos UNIQUE (position)
                   )")
    @conn.execute("CREATE TABLE examples (
                     title text NOT NULL,
                     title_prematch text,
                     title_postmatch text,
                     anchor text NOT NULL,
                     section text NOT NULL,
                     position integer NOT NULL,
                     note text,
                     CONSTRAINT example_title_section
                       PRIMARY KEY (title, section)
                     CONSTRAINT anchor_uniq
                       UNIQUE (anchor)
                     CONSTRAINT example_section
                       FOREIGN KEY (section)
                       REFERENCES sections (title)
                     CONSTRAINT section_pos_uniq
                       UNIQUE (section, position)
                   )")
  end

  def add_section(title, anchor, section_num, supersection)
    @conn.execute('INSERT INTO sections VALUES (?, ?, ?, ?)',
                  [title, anchor, section_num, supersection])
  end

  def add_example(title, anchor, section, example_num, note,
                  title_prematch, title_postmatch)
    @conn.execute('INSERT INTO examples VALUES (?, ?, ?, ?, ?, ?, ?)',
                  [title, title_prematch, title_postmatch, anchor, section,
                   example_num, note])
  rescue
    $stderr.puts "failed to insert title: #{title} anchor: #{anchor} "\
                 "section: #{section}"
    raise
  end

  def get_sections_for_supersection(supersection)
    @conn.execute('SELECT title, anchor '\
                  'FROM sections '\
                  'WHERE supersection = ? '\
                  'ORDER BY position', [supersection])
  end

  def get_examples_for_section(section)
    @conn.execute('SELECT title, title_prematch, '\
                  '       title_postmatch, anchor, note '\
                  'FROM examples '\
                  'WHERE section = ? '\
                  'ORDER BY position', [section])
  end

  def get_example_for_title_and_section(title, section)
    rows = @conn.execute('SELECT title, title_prematch, '\
                         '       title_postmatch, anchor '\
                         'FROM examples '\
                         'WHERE section = ? '\
                         '  AND title = ?', [section, title])
    rows.empty? ? nil : rows[0]
  end

  def get_section_by_title(section_title)
    rows = @conn.execute('SELECT title, anchor '\
                         'FROM sections '\
                         'WHERE title = ?', [section_title])
    rows.empty? ? nil : rows[0]
  end

  def update(table)
    supersection = nil
    section = nil
    section_num = 0
    example_num = 0

    table.each do |columns|
      if header_row?(columns)
        header_cell = columns.find { |col| !col.empty? }
        md = SUPERSECTION_CELL_REGEX.match(header_cell)
        if md
          supersection = md[1]
          next
        end
        md = HEADER_CELL_REGEX.match(header_cell)
        if md
          anchor, title = md[1..2]
          section_num += 1
          example_num = 1
          add_section(title, anchor, section_num, supersection)
          section = title
        else
          $stderr.puts("DB#update: skipping header: #{header_cell}")
        end
        next
      end
      next if EMPTY_CELL_REGEX.match(columns[1])
      md = ROW_TITLE_REGEX.match(columns[1])
      if md
        anchor, title = md[1..2]
        title_prematch = md.pre_match
        title_postmatch = md.post_match
        note = columns[3]
        add_example(title, anchor, section, example_num, note,
                    title_prematch, title_postmatch)
        example_num += 1
      elsif columns[1].start_with?('~ title')
        next
      else
        $stderr.puts("DB#update: skipping column: #{columns.join('||')}")
      end
    end
  end

  def check_title(title_cell, section)
    md = ROW_TITLE_REGEX.match(title_cell)
    if md
      # anchor = md[1]
      title = md[2]
      # pre_title = md.pre_match
      # post_title = md.post_match
      data = get_example_for_title_and_section(title, section)
      unless data
        $stderr.puts "[ERROR] not in skeleton: section: #{section} "\
                     "title: #{title}"
      end
    else
      $stderr.puts "[ERROR] not a title cell: #{title_cell}" unless md
    end
    title_cell
  end

  def check_section(section)
    data = get_section_by_title(section)
    $stderr.puts "[ERROR] not a skeleton section: #{section}" unless data
  end

  def generate_nav(output_stream)
    output_stream.write '[[# top]]'
    SUPERSECTIONS.each do |supersection|
      output_stream.write "##gray|#{supersection.downcase}:## "
      sections = []
      get_sections_for_supersection(supersection).each do |title, anchor|
        sections << "[##{anchor} #{title}]"
      end
      output_stream.puts sections.join(' | ')
      output_stream.puts
    end
  end

  def generate_table(output_stream)
    SUPERSECTIONS.each do |supersection|
      output_stream.puts "||||||~ #{supersection}||"
      get_sections_for_supersection(supersection).each do |section_data|
        section_title = section_data[0]
        section_anchor = section_data[1]
        output_stream.puts "||||||~ [[# #{section_anchor}]]"\
                           "[##{section_anchor}-note #{section_title}]||"
        output_stream.puts '||~ title ||~ anchor||~ description||'
        get_examples_for_section(section_title).each do |data|
          title, title_prematch, title_postmatch, anchor, note = *data
          output_stream.write "||#{title_prematch}[[# #{anchor}]]"\
                              "[##{anchor}-note #{title}]#{title_postmatch}"
          output_stream.write "||##{anchor}"
          output_stream.puts "||#{note}||"
        end
      end
    end
    underscores = '_' * 35
    output_stream.puts "||~ ||~ ##EFEFEF|@@#{underscores}@@##||~ ||"
  end

  def generate(output_stream)
    generate_nav(output_stream)
    generate_table(output_stream)
  end

  def close
    @conn.close
  end
end

def bar_split(line)
  inside_at_quote = false
  a = []
  tokens = line.scan(/\|\||@@|.+?(?=\|\||@@)|.+$/m)

  s = ''

  loop do
    token = tokens.shift
    break if token.nil?
    case token
    when '||'
      if inside_at_quote
        s += token
      else
        a << s
        s = ''
      end
    when '@@'
      if inside_at_quote
        inside_at_quote = false
      elsif tokens.include?('@@')
        inside_at_quote = true
      end
      s += token
    else
      s += token
    end
  end

  a << s

  a
end

def header_row?(row)
  row.select { |col| !col.empty? }.size == 1
end

def header_column(row)
  row.select { |col| !col.empty? }.first
end

def table_line?(line)
  TABLE_LINE_REGEX.match(line)
end

def end_of_table?(line)
  END_OF_TABLE_REGEX.match(line)
end

def parse(f)
  table = []
  columns = []

  before_table = true
  after_table = false
  following_continued_line = false
  in_continued_line = false

  f.each do |line|
    next if before_table && !table_line?(line)
    before_table = false

    after_table = true if !before_table && end_of_table?(line)
    next if after_table

    a = bar_split(line)

    if columns.empty?
      columns = a
    else
      columns[-1] += a.shift
      columns.concat(a)
    end

    if !CONTINUATION_REGEX.match(columns.last)
      columns[-1].chomp!
      table << columns
      columns = []
      in_continued_line = false
    else
      in_continued_line = true
    end

    break if !following_continued_line && !table_line?(line)

    following_continued_line = in_continued_line
  end

  unless columns.empty?
    columns[-1].chomp!
    table << columns
  end

  table
end

def fix_row_title(current_title)
  loop do
    $stderr.puts "current title: #{current_title}"
    $stderr.write 'new anchor: '
    anchor = $stdin.gets.chomp
    $stderr.write 'new title: '
    title = $stdin.gets.chomp
    row_title = "[[# #{anchor}]][##{anchor}-note #{title}]"
    if ROW_TITLE_REGEX.match(row_title)
      return row_title
    else
      $stderr.puts "ERROR: new row title rejected: #{row_title}"
    end
  end
end

def generate_check_header(columns, db, section)
  if header_row?(columns)
    header_cell = columns.find { |col| !col.empty? }
    md = HEADER_CELL_REGEX.match(header_cell)
    section = md[2] if md
    db.check_section(section) if db
  end
  section
end

def generate_check_row(columns, db, section)
  anchor = ''
  if !header_row?(columns) \
     && !EMPTY_CELL_REGEX.match(columns[1])
    columns[1] = db.check_title(columns[1], section) if db
    md = ROW_TITLE_REGEX.match(columns[1])
    if md
      anchor = md[1]
    else
      $stderr.puts "ERROR: no anchor in title #{columns[1]}"
    end
  end
  anchor
end

def generate_fix_row_title(columns)
  footnote = false
  return unless footnote \
                && !header_row?(columns) \
                && !EMPTY_CELL_REGEX.match(columns[1]) \
                && !ROW_TITLE_REGEX.match(columns[1])
  columns[1] = fix_row_title(columns[1])
end

def make_anchor_to_splice_columns(splice_table, db)
  return Hash.new { |h, k| h[k] = [''] } unless splice_table
  max_columns = splice_table.inject(0) { |m, o| o.size > m ? o.size : m }
  anchor_to_splice_columns = Hash.new do |h, k|
    a = [' '] * (max_columns - 2)
    a[-1] = ''
    h[k] = a
  end
  section = 'version'
  splice_table.each do |columns|
    section = generate_check_header(columns, db, section)
    anchor = generate_check_row(columns, db, section)
    next if anchor.empty?
    if anchor_to_splice_columns.key?(anchor)
      $stderr.puts "ERROR: anchor multiple times in splice table: #{anchor}"
    else
      anchor_to_splice_columns[anchor] = columns[2..-1]
    end
  end
  anchor_to_splice_columns
end

def generate(f, table, db, splice_table)
  # FIXME: keep track of and output splice columns that don't get used
  anchor_to_splice_columns = make_anchor_to_splice_columns(splice_table, db)
  anchors = {}
  section = 'version'
  max_columns = 0
  table.each do |columns|
    max_columns = columns.size if columns.size > max_columns
    section = generate_check_header(columns, db, section)
    generate_fix_row_title(columns)
    anchor = generate_check_row(columns, db, section)
    output_columns = columns[0..-2] + anchor_to_splice_columns[anchor]
    # FIXME: what about header rows?
    f.puts output_columns.join('||')
    anchors[anchor] = true unless anchor.empty?
  end

  return unless splice_table
  section = 'version'
  splice_table.each do |columns|
    section = generate_check_header(columns, db, section)
    anchor = generate_check_row(columns, db, section)
    output_columns = [''] + [' '] * (max_columns - 2) + columns[2..-1]
    output_columns[1] = columns[1]
    f.puts output_columns.join('||') unless anchors[anchor]
  end
end

def reorder(table, columns)
  columns.unshift(0)
  columns << 0

  table.map do |row|
    if header_row?(row)
      header = columns.map { '' }
      header[-2] = header_column(row)
      header
    else
      columns.map do |i|
        if i > 0 && (row[i].nil? || row[i].empty?)
          ' '
        else
          row[i]
        end
      end
    end
  end
end

def sort(table)
  table.sort { |o1, o2| o1[1] <=> o2[1] }
end

def column_count(table)
  column_cnts = Hash.new { |h, k| h[k] = 0 }
  table.each { |row| column_cnts[row.size] += 1 }

  column_cnt = nil
  num_rows = 0
  column_cnts.each do |row_size, cnt|
    if cnt > num_rows
      column_cnt = row_size
      num_rows = cnt
    end
  end

  column_cnt
end

def print_statistics(table, output_stream)
  column_cnt = nil
  header_row_cnt = 0
  non_header_row_cnt = 0
  row_title_cnt = 0

  nonempty_column_cnts = Hash.new { |h, k| h[k] = 0 }
  empty_column_cnts = Hash.new { |h, k| h[k] = 0 }

  column_cnt = column_count(table)

  table.each do |row|
    next if column_cnt && row.size != column_cnt

    if header_row?(row)
      header_row_cnt += 1
    elsif /^[~\s]*$/.match(row[1])
      # not a content row so skip
    else
      non_header_row_cnt += 1
      if ROW_TITLE_REGEX.match(row[1])
        row_title_cnt += 1
      else
        output_stream.puts "[ERROR] no anchor and footnote link: #{row[1]}"
      end
      row.each_with_index do |col, coli|
        if EMPTY_CELL_REGEX.match(col)
          empty_column_cnts[coli] += 1
        else
          nonempty_column_cnts[coli] += 1
        end
      end
    end
  end

  output_stream.puts "[INFO] header rows: #{header_row_cnt}  "\
                     "non-header rows: #{non_header_row_cnt}"
  output_stream.puts '[INFO] non-header rows with anchor and footnote link: '\
                     "#{row_title_cnt}"
  nonempty_column_cnts.keys.sort.each do |coli|
    next if coli < 2
    nonempty_cnt = nonempty_column_cnts[coli]
    pct = '%.2f' %
          (100.0 * nonempty_cnt / (nonempty_cnt + empty_column_cnts[coli]))
    lang = "column #{coli}"
    output_stream.puts "[INFO] cells in #{lang}: "\
                       "#{nonempty_column_cnts[coli]} (#{pct}%)"
  end
end

def usage
  $stderr.puts <<EOF
USAGE:
  table.rb --columns=COL1,COL2,...
           --file=PATH
           [--splice-columns=COL1,COL2,... --splice-file=PATH]
           > OUTPUT
  table.rb --parse-skeleton=PATH
           --database=PATH
EOF
  exit 1
end

if $PROGRAM_NAME == __FILE__

  opts = GetoptLong.new(
    ['--columns', '-c', GetoptLong::REQUIRED_ARGUMENT],
    ['--database', '-d', GetoptLong::REQUIRED_ARGUMENT],
    ['--generate-skeleton', GetoptLong::REQUIRED_ARGUMENT],
    ['--help', '-h', GetoptLong::NO_ARGUMENT],
    ['--parse-skeleton', GetoptLong::REQUIRED_ARGUMENT],
    ['--file', '-f', GetoptLong::REQUIRED_ARGUMENT],
    ['--splice-file', GetoptLong::REQUIRED_ARGUMENT],
    ['--splice-columns', GetoptLong::REQUIRED_ARGUMENT]
  )

  columns = []
  input_stream = $stdin
  db = nil
  skeleton_input_stream = nil
  skeleton_output_stream = nil
  splice_columns = []
  splice_input_stream = nil

  opts.each do |opt, arg|
    case opt
    when '--columns'
      columns = arg.split(',', -1).map(&:to_i)
    when '--database'
      db = DB.new(arg)
    when '--file'
      input_stream = File.open(arg)
    when '--generate-skeleton'
      skeleton_output_stream = File.open(arg, 'w')
    when '--help'
      usage
    when '--parse-skeleton'
      skeleton_input_stream = File.open(arg)
    when '--splice-columns'
      splice_columns = arg.split(',', -1).map(&:to_i)
      # FIXME: check if 1 is first column?
    when '--splice-file'
      splice_input_stream = File.open(arg)
    end
  end

  # TODO: check for conflicting flags

  if skeleton_input_stream
    skeleton = parse(skeleton_input_stream)
    db.setup
    db.update(skeleton)
    exit 0
  end

  if skeleton_output_stream
    db.generate(skeleton_output_stream)
    exit 0
  end

  usage if !columns || columns.any? { |col| col.to_i < 1 }

  if !splice_columns.empty? && splice_input_stream
    splice_table = parse(splice_input_stream)
    # FIXME: indicate which table in print_statistics?
    print_statistics(splice_table, $stderr)
  elsif !splice_columns.empty? || splice_input_stream
    $stderr.puts 'ERROR: use --splice-columns and --splice-file together'
    usage
  end

  table = parse(input_stream)
  print_statistics(table, $stderr)
  generate($stdout,
           reorder(table, columns),
           db,
           splice_table ? reorder(splice_table, splice_columns) : nil)
end
