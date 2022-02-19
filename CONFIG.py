class config(object):
    def __init__(self,filename,subgroup):
        f = open(filename, 'r')
        line = f.readlines()
        i=0

        if(subgroup == 'all')or(subgroup == 'ALL'):
            print 'The following parameters were read in from '+filename
            print

            while(i < len(line)):
                if((line[i][0] != '[') and (line[i][0] != '#') and (line[i][0] != '\n')):
                    parameter = line[i].split(' = ')[0]
                    value = line[i].split(' = ')[1].split(' #')[0]
                    try:
                        value = int(value)
                    except:
                        try:
                            value = float(value)
                        except:
                            if((value == 'True') or (value == 'true')):
                                value = True
                            elif((value == 'False') or (value == 'false')):
                                value = False
                            elif value[0] == '[':
								array = []
								subarray = []
								if value[1] == ']':	# empty array
									pass
								else:
									value = value[1:-1]
									if value[0] == '[':	# 2-D array
										value = value[1:-1]
										if value[0] == '[':	# 3-D array
											value = value[1:-1]
											#print 'value:',value
											try:
												for j in range(len(value.split(']],[['))):
													subarray = []
													for k in range(len(value.split(']],[[')[j].split('],['))):
														sub_subarray = []
														for l in range(len(value.split(']],[[')[j].split('],[')[k].split(','))):
															sub_subarray.append(int(value.split(']],[[')[j].split('],[')[k].split(',')[l]))
														subarray.append(sub_subarray)
													array.append(subarray)
											except:
												array = []
												for j in range(len(value.split(']],[['))):
													subarray = []
													for k in range(len(value.split(']],[[')[j].split('],['))):
														sub_subarray = []
														for l in range(len(value.split(']],[[')[j].split('],[')[k].split(','))):
															sub_subarray.append(float(value.split(']],[[')[j].split('],[')[k].split(',')[l]))
														subarray.append(sub_subarray)
													array.append(subarray)
										else:
											try:
												for j in range(len(value.split('],['))):
													subarray = []
													for k in range(len(value.split('],[')[j].split(','))):
														subarray.append(int(value.split('],[')[j].split(',')[k]))
													array.append(subarray)
											except:
												array = []
												for j in range(len(value.split('],['))):
													subarray = []
													for k in range(len(value.split('],[')[j].split(','))):
														subarray.append(float(value.split('],[')[j].split(',')[k]))
													array.append(subarray)
									else:
										try:
											for j in range(len(value.split(','))):
                                                                                                try:
													array.append(int(value.split(',')[j]))
												except:
													if value.split(',')[j].upper() == 'TRUE':
														array.append(True)
													elif value.split(',')[j].upper() == 'FALSE':
														array.append(False)
													else:
														array.append(value.split(',')[j])
										except:
											array = []
											for j in range(len(value.split(','))):
												array.append(float(value.split(',')[j]))
								value = array
                    setattr(self, parameter, value)
                    print '\t'+parameter+': '+str(value)
                i+=1
            print
        else:
            not_entered = 1
            print 'The following parameters were read in from '+subgroup+' of',
            if (filename == 'cmdline'):
                print 'passed configuration file:'
            else:
                print filename+'.ini:'
            print

            while((i < len(line)) and (line[i] != ('['+subgroup+']\n'))):
                i+=1
            i+=1
            while((i < len(line)) and (line[i][0] != '[')):
                not_entered = 0
                if((line[i][0] != '#') and (line[i][0] != '\n')):
                    line[i] = line[i].split(' = ')
                    parameter = line[i][0]
                    value = line[i][1].split('#' or '\t')[0]
                    try:
                        value = int(value)
                    except:
                        try:
                            value = float(value)
                        except:
                            if (i != (len(line)-1)):
                                value = value[:-1]
                            if((value == 'True') or (value == 'true')):
                                value = 1
                            if((value == 'False') or (value == 'false')):
                                value = 0
                    setattr(self, parameter, value)
                    print '\t'+parameter+': '+str(value)
                i+=1
            if not_entered:
                print
                sys.exit('Subgroup [%s] not found in %s' %(subgroup, IniFile))
                print
        f.close()
