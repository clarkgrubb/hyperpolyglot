#!/usr/bin/env ruby

require 'getoptlong'
require 'pp'

CONTINUATION_REGEX = / _$/
TABLE_LINE_REGEX = /^\s*\|\|/

HPGLOT_PAGE_AND_COLUMN_TO_LANG = {

  'c' => {
    2 => 'c',
    3 => 'go',
    4 => 'fortran',
  },

  'computer-algebra' => {
    2 => 'mathematica',
    3 => 'maxima',
    4 => 'pari/gp',
  },

  'cpp' => {
    2 => 'c++',
    3 => 'objective-c',
    4 => 'java',
    5 => 'c#',
  },

  'data' => {
    2 => 'sql',
    3 => 'awk',
    4 => 'pig',
  },

  'embeddable' => {
    2 => 'tcl',
    3 => 'lua',
    4 => 'javascript',
    5 => 'io',
  },

  'lisp' => {
    2 => 'commonlisp',
    3 => 'scheme',
    4 => 'clojure',
    5 => 'emacslisp',
  },

  'logic' => {
    2 => 'prolog',
    3 => 'erlang',
    4 => 'oz',
  },

  'ml' => {
    2 => 'sml',
    3 => 'ocaml',
    4 => 'scala',
    5 => 'haskell',
  },

  'numerical-analysis' => {
    2 => 'matlab',
    3 => 'r',
    4 => 'numpy',
  },

  'pascal' => {
    2 => 'pascal',
    3 => 'ada',
    4 => 'pl/pgsql',
  },

  'scripting' => {
    2 => 'perl',
    3 => 'php',
    4 => 'python',
    5 => 'ruby',
  },

  'scripting2' => {
    2 => 'perl',
    3 => 'php',
    4 => 'python',
    5 => 'ruby',
  },

  'shell' => {
    2 => 'posix',
    3 => 'applescript',
    4 => 'powershell',
  },

  'stack' => {
    2 => 'forth',
    3 => 'postscript',
    4 => 'factor',
  },
}


def bar_split(line)

  inside_at_quote = false
  a = []
  tokens = line.scan(/\|\||@@|.+?(?=\|\||@@)|.+$/m)

  s = ""

  loop do
    token = tokens.shift
    break if token.nil?
    case token
    when '||'
      if inside_at_quote
        s += token
      else
        a << s
        s = ""
      end
    when '@@'
      if inside_at_quote
        inside_at_quote = false
      elsif tokens.include?('@@')
        inside_at_quote = true
      else
        # unmatched starting @@
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
  row.select { |col| not col.empty? }.size == 1
end

def header_column(row)
  row.select { |col| not col.empty? }.first
end

def table_line?(line)
  TABLE_LINE_REGEX.match(line)
end

def parse(f, extract_table)

  table = []
  columns = []

  before_table = true
  following_continued_line = false
  in_continued_line = false

  f.each do |line|

    next if extract_table and before_table and not table_line?(line)
    before_table = false

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

    if extract_table and not following_continued_line and not table_line?(line)
      break
    end

    following_continued_line = in_continued_line

  end

  unless columns.empty?
    columns[-1].chomp!
    table << columns
  end

  table
end

def generate(f, table)

  table.each do |columns|
    f.puts columns.join('||')
  end
end

def reorder(table, columns)

  columns.unshift(0)
  columns << 0

  table.map do |row|
    if header_row?(row)
      header = columns.map { |i| "" }
      header[-2] = header_column(row)
      header
    else
      columns.map do |i|
        if i > 0 and (row[i].nil? or row[i].empty?)
          " "
        else
          row[i]
        end
      end
    end
  end
end

def sort(table)
  table.sort { |o1,o2| o1[1] <=> o2[1] }
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

def print_statistics(table, page)

  column_cnt = nil
  header_row_cnt = 0
  non_header_row_cnt = 0

  nonempty_column_cnts = Hash.new { |h, k| h[k] = 0 }
  empty_column_cnts = Hash.new { |h, k| h[k] = 0 }

  column_cnt = column_count(table)

  if page
    column_to_lang = HPGLOT_PAGE_AND_COLUMN_TO_LANG[page]
  end

  column_to_lang = {} if column_to_lang.nil?

  table.each do |row|

    next if column_cnt and row.size != column_cnt

    if header_row?(row)
      header_row_cnt += 1
    elsif /^[~\s]*$/.match(row[1])
      # not a content row so skip
    else
      non_header_row_cnt += 1
      row.each_with_index do |col, coli|
        if /^\s*$/.match(col)
          empty_column_cnts[coli] += 1
        else
          nonempty_column_cnts[coli] += 1
        end
      end
    end
  end

  puts "#{page} header rows: #{header_row_cnt} non-header rows: #{non_header_row_cnt}"
  nonempty_column_cnts.keys.sort.each do |coli|
    next if coli < 2
    nonempty_cnt = nonempty_column_cnts[coli]
    pct = "%.2f" % (100.0 * nonempty_cnt / (nonempty_cnt + empty_column_cnts[coli]))
    lang = column_to_lang[coli]
    lang = "column #{coli}" if lang.nil?
    puts "cells in #{lang} #{nonempty_column_cnts[coli]} (#{pct}%)"
  end


end

def usage
  $stderr.puts "table.rb --sort --columns=COL1,COL2,... < INPUT"
  exit -1
end

if $0 == __FILE__

  opts = GetoptLong.new(
                        [ '--columns', "-c", GetoptLong::REQUIRED_ARGUMENT ],
                        [ '--sort', "-s", GetoptLong::NO_ARGUMENT ],
                        [ '--statistics', "-t", GetoptLong::NO_ARGUMENT ],
                        [ '--extract', "-x", GetoptLong::NO_ARGUMENT ],
                        [ '--page', "-p", GetoptLong::REQUIRED_ARGUMENT ]
                        )

  columns = []
  page = nil
  sort_table = false
  statistics = false
  extract_table = false

  opts.each do |opt,arg|
    case opt
    when '--columns'
      columns = arg.split(',',-1).map { |s| s.to_i }
    when '--sort'
      sort_table = true
    when '--statistics'
      statistics = true
    when '--extract'
      extract_table = true
    when '--page'
      page = arg
    end
  end

  usage if not statistics and columns.empty?
  usage if not statistics and columns.any? { |col| col.to_i < 1 }

  table = parse($stdin, extract_table)

  if statistics
    print_statistics(table, page)
    exit(0)
  end

  if sort_table
    table = sort(table)
  end

  generate($stdout, reorder(table, columns))

end
