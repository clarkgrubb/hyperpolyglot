#!/usr/bin/env ruby

require 'getoptlong'
require 'pp'
require 'sqlite3'

CONTINUATION_REGEX = / _$/
TABLE_LINE_REGEX = /^\s*\|\|/
END_OF_TABLE_REGEX = /^\s*$/
ROW_TITLE_REGEX =
  /\[\[# ([a-z][a-z0-9-]*)\]\]\[#\1-note ([A-Za-z0-9? \.\/,-]+)\]/
EMPTY_CELL_REGEX = /^([~\s]*|~ \[\[# [a-z-]+\]\])$/
HEADER_CELL_REGEX = /^~ \[\[# ([a-z-]+)\]\]\[#\1-note ([^\]]+)\]$/

class DB
  def initialize(path)
    @conn = SQLite3::Database.new path
  end

  def setup
    @conn.execute("CREATE TABLE sections (
                     title text PRIMARY KEY,
                     anchor text NOT NULL,
                     position integer NOT NULL,
                     CONSTRAINT pos UNIQUE (position)
                   )")
    @conn.execute("CREATE TABLE examples (
                     title text NOT NULL,
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

  def add_section(title, anchor, section_num)
    @conn.execute('INSERT INTO sections VALUES (?, ?, ?)',
                  [title, anchor, section_num])
  end

  def add_example(title, anchor, section, example_num, note)
    @conn.execute('INSERT INTO examples VALUES (?, ?, ?, ?, ?)',
                  [title, anchor, section, example_num, note])
  rescue
    $stderr.puts "failed to insert title: #{title} anchor: #{anchor} "\
                 "section: #{section}"
    raise
  end

  def update(table)
    section = 'general'
    section_num = 1
    example_num = 1
    add_section(section, section, section_num)

    table.each do |columns|
      if header_row?(columns)
        header_cell = columns.find { |col| !col.empty? }
        md = HEADER_CELL_REGEX.match(header_cell)
        if md
          anchor, title = md[1..2]
          section_num += 1
          example_num = 1
          add_section(title, anchor, section_num)
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
        note = columns[3]
        add_example(title, anchor, section, example_num, note)
        example_num += 1
      else
        $stderr.puts("DB#update: skipping column: #{columns.join('||')}")
      end
    end
  end

  def generate
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

def generate(f, table)
  footnote = false

  table.each do |columns|
    if footnote \
      && !header_row?(columns) \
      && !EMPTY_CELL_REGEX.match(columns[1]) \
      && !ROW_TITLE_REGEX.match(columns[1])
      columns[1] = fix_row_title(columns[1])
    end
    f.puts columns.join('||')
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
        output_stream.puts "INFO: no anchor and footnote link: #{row[1]}"
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

  output_stream.puts "header rows: #{header_row_cnt}  "\
                     "non-header rows: #{non_header_row_cnt}"
  output_stream.puts 'non-header rows with anchor and footnote link: '\
                     "#{row_title_cnt}"
  nonempty_column_cnts.keys.sort.each do |coli|
    next if coli < 2
    nonempty_cnt = nonempty_column_cnts[coli]
    pct = '%.2f' %
          (100.0 * nonempty_cnt / (nonempty_cnt + empty_column_cnts[coli]))
    lang = "column #{coli}"
    output_stream.puts "cells in #{lang}: #{nonempty_column_cnts[coli]} "\
                       "(#{pct}%)"
  end
end

def usage
  $stderr.puts <<EOF
USAGE:
  table.rb --columns=COL1,COL2,...
           --file=PATH
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
    ['--file', '-f', GetoptLong::REQUIRED_ARGUMENT]
  )

  columns = []
  input_stream = $stdin
  db = nil
  skeleton_input_stream = nil
  skeleton_output_stream = nil

  opts.each do |opt, arg|
    case opt
    when '--columns'
      columns = arg.split(',', -1).map(&:to_i)
    when '--database'
      db = DB.new(arg)
      $stderr.puts 'DEBUG: created db'
    when '--file'
      input_stream = File.open(arg)
    when '--generate-skeleton'
      skeleton_output_stream = File.open(arg, 'w')
    when '--help'
      usage
    when '--parse-skeleton'
      skeleton_input_stream = File.open(arg)
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

  table = parse(input_stream)
  print_statistics(table, $stderr)
  generate($stdout, reorder(table, columns))
end
