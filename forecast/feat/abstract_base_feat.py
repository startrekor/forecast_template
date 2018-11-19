# coding:utf-8"""__file__    base_feat.py__description__    This file provides modules for combining features and save them in svmlight format.__author__    songquanwang"""import abcimport osimport pickleimport numpy as npimport pandas as pdfrom scipy.sparse import hstackfrom sklearn.datasets import dump_svmlight_fileimport forecast.conf.model_params_conf as configfrom forecast.feat.nlp import ngramfrom forecast.feat.nlp.nlp_utils import preprocess_datafrom forecast.interface.feat_inter import FeatInterclass AbstractBaseFeat(FeatInter):    __metaclass__ = abc.ABCMeta    @staticmethod    def gen_column_gram(df):        """        用户组合其他特征的临时特征，这些基本特征会用到        :param df:        :return:        """        # unigram 生成单个词根        print("generate unigram")        df["query_unigram"] = list(df.apply(lambda x: preprocess_data(x["query"]), axis=1))        df["title_unigram"] = list(df.apply(lambda x: preprocess_data(x["product_title"]), axis=1))        df["description_unigram"] = list(df.apply(lambda x: preprocess_data(x["product_description"]), axis=1))        # bigram 生成二元字根，用_连接        print("generate bigram")        join_str = "_"        df["query_bigram"] = list(df.apply(lambda x: ngram.getBigram(x["query_unigram"], join_str), axis=1))        df["title_bigram"] = list(df.apply(lambda x: ngram.getBigram(x["title_unigram"], join_str), axis=1))        df["description_bigram"] = list(df.apply(lambda x: ngram.getBigram(x["description_unigram"], join_str), axis=1))        # trigram 生成三元字根，用_连接        print("generate trigram")        join_str = "_"        df["query_trigram"] = list(df.apply(lambda x: ngram.getTrigram(x["query_unigram"], join_str), axis=1))        df["title_trigram"] = list(df.apply(lambda x: ngram.getTrigram(x["title_unigram"], join_str), axis=1))        df["description_trigram"] = list(df.apply(lambda x: ngram.getTrigram(x["description_unigram"], join_str), axis=1))        return df    def generate_dist_stats_feat(self, dist_metric, X_train, ids_train, X_test, ids_test, indices_dict, qids_test=None):        """        生成距离状态特征，每一行是一个向量，计算行与各个类别的行之间        相互距离的最小值，中位数、最大值、平均值、方差        如果qids_test不为空，则每个test和与他相同的qid的类别做比较        :param dist_metric: 距离度量标准 cosine/euclidean        :param X_train:        :param ids_train:        :param X_test:        :param ids_test:        :param indices_dict: 类别键值字典        :param qids_test: 类别+qid键值字典        :return: len(ids_test) 行 stats_feat_num*n_classes列的矩阵---20个列        每行test-跟-某个类别的train 多对多距离，求距离的 五个统计指标        每行test-跟-某个类别的train 多对多距离，求距离的 五个统计指标        stats_func ：全局函数        stats_feat_num：全局        """        # 生成 len(ids_test)行，class(分类个数)列的 多维数组        stats_feat = np.zeros((len(ids_test), self.stats_feat_num * config.num_of_class), dtype=float)        dis = self.pairwise_dist(X_test, X_train, dist_metric)        for i in range(len(ids_test)):            id = ids_test[i]            if qids_test is not None:                qid = qids_test[i]            # 一行分别于某一类的距离做比较            for j in range(config.num_of_class):                # if赋值语句                key = (qid, j + 1) if qids_test is not None else j + 1                if indices_dict.has_key(key):                    inds = indices_dict[key]                    # exclude this sample itself from the list of indices                    inds = [ind for ind in inds if id != ids_train[ind]]                    sim_tmp = dis[i][inds]                    if len(sim_tmp) != 0:                        # 距离的平均值、方差                        feat = [func(sim_tmp) for func in self.stats_func]                        #quantile                        sim_tmp = pd.Series(sim_tmp)                        # 距离的最小值、中位数、最大值                        quantiles = sim_tmp.quantile(self.quantiles_range)                        feat = np.hstack((feat, quantiles))                        # 每一行生成 [五个值的数组]                        stats_feat[i, j * self.stats_feat_num:(j + 1) * self.stats_feat_num] = feat        return stats_feat    @staticmethod    def get_sample_indices_by_relevance(dfTrain, additional_key=None):        """        return a dict with        key: (additional_key, median_relevance)        val: list of sample indices，也就是从零开始的行号        :param dfTrain:        :param additional_key: qid        :return:        """        # 从零开始编号        dfTrain["sample_index"] = range(dfTrain.shape[0])        group_key = ["median_relevance"]        # 按照相关性、qid分组        if additional_key != None:            group_key.insert(0, additional_key)        # 根据相关性分组 每组序号放到[]里        agg = dfTrain.groupby(group_key, as_index=False).apply(lambda x: list(x["sample_index"]))        # 生成相关性为键的字典        d = dict(agg)        dfTrain = dfTrain.drop("sample_index", axis=1)        return d    @staticmethod    def dump_feat_name(feat_names, feat_name_file):        """            save feat_names to feat_name_file        """        with open(feat_name_file, "wb") as f:            for i, feat_name in enumerate(feat_names):                if feat_name.startswith("count") or feat_name.startswith("pos_of"):                    f.write("('%s', SimpleTransform(config.count_feat_transform)),\n" % feat_name)                else:                    f.write("('%s', SimpleTransform()),\n" % feat_name)    @staticmethod    def extract_feats(base_feat_path, info_path, save_path, feat_names, mode):        """        :param base_feat_path:        :param info_path:        :param save_path:        :param feat_names:        :param mode:        :return:        """        if not os.path.exists(save_path):            os.makedirs(save_path)        for i, (feat_name, transformer) in enumerate(feat_names):            # load train feat            feat_train_file = "%s/train.%s.feat.pkl" % (base_feat_path, feat_name)            with open(feat_train_file, "rb") as f:                x_train = pickle.load(f)            if len(x_train.shape) == 1:                x_train = x_train.reshape((x_train.shape[0], 1))            ## load test feat            feat_test_file = "%s/%s.%s.feat.pkl" % (base_feat_path, mode, feat_name)            with open(feat_test_file, "rb") as f:                x_test = pickle.load(f)            if len(x_test.shape) == 1:                x_test = x_test.reshape((x_test.shape[0], 1))            ## align feat dim 补齐列？matrix hstack  tocsr 稀疏格式            dim_diff = abs(x_train.shape[1] - x_test.shape[1])            if x_test.shape[1] < x_train.shape[1]:                x_test = hstack([x_test, np.zeros((x_test.shape[0], dim_diff))]).tocsr()            elif x_test.shape[1] > x_train.shape[1]:                x_train = hstack([x_train, np.zeros((x_train.shape[0], dim_diff))]).tocsr()            # apply transformation            x_train = transformer.fit_transform(x_train)            x_test = transformer.transform(x_test)            # stack feat 多个属性列组合在一起            if i == 0:                X_train, X_test = x_train, x_test            else:                try:                    X_train, X_test = hstack([X_train, x_train]), hstack([X_test, x_test])                except:                    X_train, X_test = np.hstack([X_train, x_train]), np.hstack([X_test, x_test])            # > 右对齐 自动填充{}            print("Combine {:>2}/{:>2} feat: {} ({}D)".format(i + 1, len(feat_names), feat_name, x_train.shape[1]))        print("Feat dim: {}D".format(X_train.shape[1]))        # train info 中获取label值        info_train = pd.read_csv("%s/train.info" % (info_path))        # change it to zero-based for multi-classification in xgboost        Y_train = info_train["median_relevance"] - 1        # test        info_test = pd.read_csv("%s/%s.info" % (info_path, mode))        Y_test = info_test["median_relevance"] - 1        # dump feat 生成所有的特征+label        dump_svmlight_file(X_train, Y_train, "%s/train.feat" % (save_path))        dump_svmlight_file(X_test, Y_test, "%s/%s.feat" % (save_path, mode))    @staticmethod    def extract_feats_cv(feat_names, feat_path_name):        """        function to combine features        """        print("==================================================")        print("Combine features...")        # Cross-validation        print("For cross-validation...")        ## for each run and fold  把没Run每折train.%s.feat.pkl　文件读出来合并到一起　然后保存到        for run in range(1, config.n_runs + 1):            # use 33% for training and 67 % for validation, so we switch trainInd and validInd            for fold in range(1, config.n_folds + 1):                print("Run: %d, Fold: %d" % (run, fold))                # 单个feat path                base_feat_path = "%s/Run%d/Fold%d" % (config.solution_feat_base, run, fold)                # 合并后的feat path                save_path = "%s/%s/Run%d/Fold%d/feat" % (config.solution_output, feat_path_name, run, fold)                info_path = "%s/Run%d/Fold%d" % (config.solution_info, run, fold)                AbstractBaseFeat.extract_feats(base_feat_path, info_path, save_path, feat_names, "valid")        # Training and Testing        print("For training and testing...")        base_feat_all_path = "%s/All" % (config.solution_feat_base)        info_all_path = "%s/All" % (config.solution_info)        save_path = "%s/%s/All/feat" % (config.solution_output, feat_path_name)        AbstractBaseFeat.extract_feats(base_feat_all_path, info_all_path, save_path, feat_names, "test")