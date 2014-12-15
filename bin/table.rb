#!/usr/bin/env ruby

require 'getoptlong'
require 'pp'

CONTINUATION_REGEX = / _$/
TABLE_LINE_REGEX = /^\s*\|\|/
END_OF_TABLE_REGEX = /^\s*$/

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

    next if before_table and not table_line?(line)
    before_table = false

    after_table = true if not before_table and end_of_table?(line)
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

    if not following_continued_line and not table_line?(line)
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

def print_statistics(table, output_stream)

  column_cnt = nil
  header_row_cnt = 0
  non_header_row_cnt = 0

  nonempty_column_cnts = Hash.new { |h, k| h[k] = 0 }
  empty_column_cnts = Hash.new { |h, k| h[k] = 0 }

  column_cnt = column_count(table)

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

  output_stream.puts "header rows: #{header_row_cnt} non-header rows: #{non_header_row_cnt}"
  nonempty_column_cnts.keys.sort.each do |coli|
    next if coli < 2
    nonempty_cnt = nonempty_column_cnts[coli]
    pct = "%.2f" % (100.0 * nonempty_cnt / (nonempty_cnt + empty_column_cnts[coli]))
      lang = "column #{coli}"
    output_stream.puts "cells in #{lang}: #{nonempty_column_cnts[coli]} (#{pct}%)"
  end


end

def usage
  $stderr.puts "table.rb --sort --columns=COL1,COL2,... < INPUT"
  exit -1
end

if $0 == __FILE__

  opts = GetoptLong.new(
                        [ '--columns', "-c", GetoptLong::REQUIRED_ARGUMENT ],
                        )

  columns = []
  page = nil
  statistics = false

  opts.each do |opt,arg|
    case opt
    when '--columns'
      columns = arg.split(',',-1).map { |s| s.to_i }
    end
  end

  usage if not statistics and columns.empty?
  usage if not statistics and columns.any? { |col| col.to_i < 1 }

  table = parse($stdin)

  print_statistics(table, $stderr)

  generate($stdout, reorder(table, columns))

end
