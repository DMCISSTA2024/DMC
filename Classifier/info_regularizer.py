import numpy as np
import torch
import torch.nn as nn
import torch.nn.functional as F


class CLUB(nn.Module):  # CLUB: Mutual Information Contrastive Learning Upper Bound
    def __init__(self, x_dim, y_dim, lr=1e-3, beta=0):
        super(CLUB, self).__init__()
        self.hiddensize = y_dim
        self.version = 2
        self.beta = beta

    def mi_est_sample(self, x_samples, y_samples):
        sample_size = y_samples.shape[0]
        random_index = torch.randint(sample_size, (sample_size,)).long()

        positive = torch.zeros_like(y_samples)
        negative = - (y_samples - y_samples[random_index]) ** 2 / 2.
        upper_bound = (positive.sum(dim=-1) - negative.sum(dim=-1)).mean()
        # return upper_bound/2.
        return upper_bound

    def mi_est(self, x_samples, y_samples):  # [nsample, 1]
        positive = torch.zeros_like(y_samples)

        prediction_1 = y_samples.unsqueeze(1)  # [nsample,1,dim]
        y_samples_1 = y_samples.unsqueeze(0)  # [1,nsample,dim]
        negative = - ((y_samples_1 - prediction_1) ** 2).mean(dim=1) / 2.   # [nsample, dim]
        return (positive.sum(dim=-1) - negative.sum(dim=-1)).mean()
        # return (positive.sum(dim = -1) - negative.sum(dim = -1)).mean(), positive.sum(dim = -1).mean(), negative.sum(dim = -1).mean()

    def loglikeli(self, x_samples, y_samples):
        return 0

    def update(self, x_samples, y_samples, steps=None):
        # no performance improvement, not enabled
        if steps:
            beta = self.beta if steps > 1000 else self.beta * steps / 1000  # beta anealing
        else:
            beta = self.beta

        return self.mi_est_sample(x_samples, y_samples) * self.beta




class InfoNCE(nn.Module):
    def __init__(self, x_dim, y_dim):
        super(InfoNCE, self).__init__()
        self.lower_size = 300
        self.F_func = nn.Sequential(nn.Linear(x_dim + y_dim, self.lower_size),
                                    nn.ReLU(),
                                    nn.Linear(self.lower_size, 1),
                                    nn.Softplus())

    def forward(self, x_samples, y_samples):  # samples have shape [sample_size, dim]
        # shuffle and concatenate
        sample_size = y_samples.shape[0]
        random_index = torch.randint(sample_size, (sample_size,)).long()
        print(sample_size,len(x_samples))
        x_tile = x_samples.unsqueeze(0).repeat((sample_size, 1, 1))
        y_tile = y_samples.unsqueeze(1).repeat((1, sample_size, 1))

        T0 = self.F_func(torch.cat([x_samples, y_samples], dim=-1))
        T1 = self.F_func(torch.cat([x_tile, y_tile], dim=-1))  # [s_size, s_size, 1]

        lower_bound = T0.mean() - (T1.logsumexp(dim = 1).mean() - np.log(sample_size))  # torch.log(T1.exp().mean(dim = 1)).mean()

        # compute the negative loss (maximise loss == minimise -loss)
        return lower_bound

    # def learning_loss(self, x_samples, y_samples):
    #     return -self.forward(x_samples, y_samples)      #存疑

# class InfoNCE(nn.Module):
#     def __init__(self, x_dim, y_dim, hidden_size=300):
#         super(InfoNCE, self).__init__()
#         self.F_func = nn.Sequential(
#             nn.Linear(x_dim + y_dim, hidden_size),
#             nn.ReLU(),
#             nn.Linear(hidden_size, 1),
#             nn.Softplus()
#         )

#     def forward(self, x_samples, y_samples):
#         # x_samples, y_samples are expected to be of shape [batch_size, seq_len, embed_dim]
#         batch_size, seq_len, embed_dim = x_samples.shape

#         # Reshape: [batch_size * seq_len, embed_dim]
#         x_samples = x_samples.view(-1, embed_dim)
#         y_samples = y_samples.view(-1, embed_dim)

#         # Positive samples
#         positive_pairs = torch.cat((x_samples, y_samples), dim=1)
#         positives = self.F_func(positive_pairs).squeeze()

#         # Negative samples
#         # Repeat x and y to create negative pairs
#         x_repeated = x_samples.unsqueeze(1).repeat(1, batch_size * seq_len, 1).view(-1, embed_dim)
#         y_repeated = y_samples.repeat(batch_size * seq_len, 1)

#         negative_pairs = torch.cat((x_repeated, y_repeated), dim=1)
#         negatives = self.F_func(negative_pairs).view(batch_size * seq_len, -1)

#         # Calculating InfoNCE loss
#         negatives = negatives - torch.diag(negatives).unsqueeze(1).expand_as(negatives)
#         negatives = torch.cat((positives.unsqueeze(1), negatives), dim=1)
#         loss = -torch.log_softmax(negatives, dim=1)[:, 0].mean()

#         return loss






def get_seq_len(attention_masks):
    lengths = torch.sum(attention_masks, dim=-1)
    return lengths.detach().cpu().numpy()


def train_mi_upper_estimator(mi_upper_estimator, infonce_estimator, hidden_states, attention_masks=None):

    last_hidden, embedding_layer = hidden_states[-1], hidden_states[0]  # embedding layer: batch x seq_len x 768 # hidden_states是各层输出，第一层是嵌入层最后一层是last hidden
    embeddings = []
    lengths = get_seq_len(attention_masks)  #数组，存储12个样本的一维输入attention_mask的有效长度（样本的特征操作码长度）
    for i, length in enumerate(lengths):
        embeddings.append(embedding_layer[i, :length])
    embeddings = torch.cat(embeddings)  # [-1, 768]   embeddings without masks 拼接得到整体的不带填充位置的嵌入向量，其中-1表示张量的第一维将根据实际情况进行自动调整。



    # loss_model = InfoNCE(768, 768).cuda()
    # loss = loss_model(embedding_layer, last_hidden)   
    return mi_upper_estimator.update(embedding_layer, embeddings) #+ loss #+ infonce_estimator.forward(embedding_layer, embeddings)